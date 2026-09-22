"""Native lightweight Ollama client using Python's built-in urllib.request."""

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from zoe.models.base import LocalModel, ModelResponse, ToolCall
from zoe.macos.logger import zoe_logger


class OllamaModel(LocalModel):
    """
    100% local model provider communicating with Ollama REST API.
    Zero external SDK dependencies.
    """

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11434",
        model_name: str = "qwen3:14b",
        timeout: float = 60.0,
        default_temperature: float = 0.1,
        default_max_tokens: int = 2048,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

    def is_available(self) -> bool:
        """Verify that local Ollama daemon is running and the configured model is installed."""
        try:
            url = f"{self.endpoint}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as response:
                data = json.loads(response.read().decode("utf-8"))

            available_models = [m.get("name", "") for m in data.get("models", [])]
            # Match exact or prefix (e.g. qwen3:14b or qwen3-coder:30b)
            clean_target = self.model_name.lower().strip()
            for m in available_models:
                m_clean = m.lower()
                if clean_target == m_clean or clean_target in m_clean:
                    return True
            return False
        except Exception:
            return False

    def model_info(self) -> Dict[str, Any]:
        """Metadata for local privacy status report."""
        available = self.is_available()
        return {
            "provider": "Ollama",
            "model": self.model_name,
            "endpoint": self.endpoint,
            "status": "AVAILABLE" if available else "UNAVAILABLE",
            "inference": "LOCAL",
            "network_ai": "DISABLED",
        }

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ModelResponse:
        """
        Send a chat completion request to Ollama /api/chat.
        Accepts optional function tool schemas and parses tool calls cleanly.
        """
        url = f"{self.endpoint}/api/chat"

        opts: Dict[str, Any] = {
            "temperature": temperature if temperature is not None else self.default_temperature,
            "num_predict": max_tokens if max_tokens is not None else self.default_max_tokens,
            "num_ctx": 4096,
        }

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": opts,
        }

        if tools:
            payload["tools"] = tools
            payload["think"] = False
            opts["think"] = False

        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            zoe_logger.log_action("MODEL_CONNECTION_ERROR", error=str(e), model=self.model_name)
            raise ConnectionError(
                f"Failed to connect to local Ollama server at {self.endpoint}. "
                "Ensure Ollama is running locally via `ollama serve`."
            ) from e

        msg = raw_data.get("message", {})
        content = msg.get("content", "") or ""
        thinking = msg.get("thinking", "") or ""
        raw_tool_calls = msg.get("tool_calls", [])

        parsed_calls: List[ToolCall] = []

        # 1. Parse native tool calls
        for idx, tc in enumerate(raw_tool_calls):
            fn_dict = tc.get("function", {})
            name = fn_dict.get("name", "")
            raw_args = fn_dict.get("arguments", {})

            # Arguments might be pre-parsed dict or stringified JSON
            args_dict: Dict[str, Any] = {}
            if isinstance(raw_args, dict):
                args_dict = raw_args
            elif isinstance(raw_args, str):
                try:
                    args_dict = json.loads(raw_args)
                except Exception:
                    args_dict = {}

            call_id = tc.get("id") or f"call_{idx}_{name}"
            parsed_calls.append(ToolCall(id=call_id, name=name, arguments=args_dict))

        # 2. Fallback heuristic: check if model generated JSON tool call in content
        if not parsed_calls and "```json" in content:
            parsed_calls.extend(self._extract_json_tool_calls_from_text(content))

        return ModelResponse(
            text=content.strip(),
            thinking=thinking.strip(),
            tool_calls=parsed_calls,
            raw=raw_data,
        )

    def _extract_json_tool_calls_from_text(self, text: str) -> List[ToolCall]:
        """Extract tool call if model emitted raw JSON markdown instead of native tool_calls."""
        calls: List[ToolCall] = []
        pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        matches = re.findall(pattern, text, re.DOTALL)
        for idx, m in enumerate(matches):
            try:
                data = json.loads(m)
                if "name" in data and ("arguments" in data or "parameters" in data):
                    name = data["name"]
                    args = data.get("arguments") or data.get("parameters") or {}
                    calls.append(ToolCall(id=f"call_text_{idx}", name=name, arguments=args))
            except Exception:
                pass
        return calls
