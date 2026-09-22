"""Observe-Think-Act agent loop for Zoe."""

import json
import time
from typing import Any, Dict, List, Optional
from zoe.config import get_config
from zoe.agent.prompts import get_system_prompt
from zoe.agent.state import AgentState
from zoe.models.base import LocalModel, ModelResponse, ToolCall
from zoe.tools.registry import tool_registry
from zoe.macos.emergency import emergency_controller
from zoe.macos.logger import zoe_logger


class AgentLoop:
    """
    Executes the continuous observe -> think -> act -> verify loop.
    Coordinates between LocalModel and Phase 1 ToolRegistry.
    """

    def __init__(self, model: LocalModel) -> None:
        self.model = model
        self.config = get_config()

    def run(self, task: str) -> AgentState:
        """
        Execute a natural-language task to completion.
        Returns final AgentState.
        """
        state = AgentState(task=task)
        zoe_logger.log_action("AGENT_START_TASK", task=task)

        # 1. Safety Guard: Check if entire task is destructive
        from zoe.agent.safety import SafetyGuard
        is_destructive, reason = SafetyGuard.is_destructive_task(task)
        if is_destructive:
            msg = f"Operation cancelled: {reason}. Destructive actions require explicit confirmation."
            state.mark_cancelled(msg)
            zoe_logger.log_action("AGENT_SAFETY_BLOCKED", task=task, reason=reason)
            return state

        # 2. Preflight Emergency Stop check
        if emergency_controller.is_stopped():
            state.mark_cancelled("Emergency stop was already active")
            return state

        # 3. Build initial conversation messages
        system_content = get_system_prompt(self.config.agent.system_prompt_extra)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": task},
        ]

        tools = tool_registry.get_schema_definitions()
        start_time = time.time()
        max_calls = self.config.agent.max_tool_calls
        timeout = self.config.agent.timeout_seconds

        while not state.is_complete:
            # Check Emergency Stop
            if emergency_controller.is_stopped():
                state.mark_cancelled("Emergency stop (ESC) triggered by user")
                zoe_logger.log_action("AGENT_CANCELLED_EMERGENCY_STOP", task=task)
                break

            # Check timeout
            if time.time() - start_time > timeout:
                state.mark_cancelled(f"Task exceeded timeout limit of {timeout}s")
                zoe_logger.log_action("AGENT_TIMEOUT", task=task)
                break

            # Check iteration limit
            if state.iteration_count >= max_calls:
                state.mark_cancelled(f"Task exceeded maximum tool call limit ({max_calls})")
                zoe_logger.log_action("AGENT_MAX_ITERATIONS", task=task)
                break

            # Repetition loop detection
            if state.history.check_repetition_loop(threshold=3):
                state.mark_cancelled("Execution halted: repeated failed actions detected (loop prevention).")
                zoe_logger.log_action("AGENT_REPETITION_LOOP_HALTED", task=task)
                break

            state.iteration_count += 1
            zoe_logger.log_action("AGENT_THINK", iteration=state.iteration_count)

            # 4. Model inference
            try:
                model_resp: ModelResponse = self.model.chat(
                    messages=messages,
                    tools=tools,
                    temperature=self.config.model.temperature,
                    max_tokens=self.config.model.max_tokens,
                )
            except Exception as e:
                err_msg = f"Local model error: {str(e)}"
                state.mark_cancelled(err_msg)
                zoe_logger.log_action("AGENT_MODEL_ERROR", error=str(e))
                break

            # 5. Handle model response
            if model_resp.has_tool_calls():
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": model_resp.text,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": tc.arguments,
                            },
                        }
                        for tc in model_resp.tool_calls
                    ],
                }
                messages.append(assistant_msg)

                # Execute each requested tool call
                for tc in model_resp.tool_calls:
                    if emergency_controller.is_stopped():
                        state.mark_cancelled("Emergency stop (ESC) triggered before tool execution")
                        break

                    # Validate tool execution safety
                    is_safe, warn_reason = SafetyGuard.validate_tool_execution(tc.name, tc.arguments)
                    if not is_safe:
                        tool_result = {"success": False, "error": f"Safety restriction: {warn_reason}"}
                        state.record_action(tc.name, tc.arguments, tool_result)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tc.name,
                            "content": json.dumps(tool_result),
                        })
                        continue

                    zoe_logger.log_action("AGENT_EXECUTE_TOOL", tool=tc.name, arguments=tc.arguments)

                    # Execute strictly through ToolRegistry
                    tool_result = tool_registry.execute(tc.name, **tc.arguments)

                    # Determine verification status
                    is_verified = False
                    if tc.name in ("inspect_screen", "get_windows", "get_active_app"):
                        is_verified = tool_result.get("success", False)
                    elif tc.name == "find_on_screen":
                        is_verified = tool_result.get("found", False)

                    state.record_action(tc.name, tc.arguments, tool_result, verified=is_verified)

                    # Context compaction: avoid giant payloads in model conversation history
                    content_str = json.dumps(tool_result)
                    if len(content_str) > 1500:
                        compact_result = dict(tool_result)
                        if "tree" in compact_result:
                            compact_result["tree"] = f"<Accessibility tree summary: app={compact_result.get('app')}>"
                        if "windows" in compact_result and len(compact_result["windows"]) > 5:
                            compact_result["windows"] = compact_result["windows"][:5]
                        content_str = json.dumps(compact_result)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": content_str,
                    })

                if state.cancelled:
                    break

            else:
                final_text = model_resp.text or "Done."
                state.mark_complete(final_text)
                zoe_logger.log_action("AGENT_TASK_COMPLETE", response=final_text[:60])
                break

        return state
