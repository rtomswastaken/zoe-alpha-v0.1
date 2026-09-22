"""Pre-flight verification for Ollama with Phase 1 tool schemas."""

import json
import urllib.request
from zoe.tools.registry import tool_registry

OLLAMA_BASE = "http://127.0.0.1:11434"

def test_ollama_tags():
    print("1. Checking /api/tags for qwen3:14b...")
    req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    
    models = [m.get("name") for m in data.get("models", [])]
    print(f"   Available models in Ollama: {models}")
    assert any("qwen3:14b" in m for m in models), "qwen3:14b not found in Ollama"
    print("   -> qwen3:14b verified available!")

def test_basic_chat():
    print("\n2. Sending basic chat message to qwen3:14b...")
    payload = {
        "model": "qwen3:14b",
        "messages": [{"role": "user", "content": "Say hello to Zoe in one short sentence."}],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 100}
    }
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        res = json.loads(response.read().decode("utf-8"))
    msg = res.get("message", {}).get("content", "")
    print(f"   Response from qwen3:14b: {msg.strip()}")
    assert len(msg) > 0, "No content returned"
    print("   -> Basic chat verified!")

def test_tool_calling():
    print("\n3. Testing tool calling with Phase 1 tool schemas...")
    schemas = tool_registry.get_schema_definitions()
    print(f"   Sending {len(schemas)} Phase 1 tool schemas to Ollama...")

    payload = {
        "model": "qwen3:14b",
        "messages": [
            {
                "role": "system",
                "content": "You are Zoe, an AI computer assistant. When the user asks you to interact with the Mac, use the provided tools."
            },
            {
                "role": "user",
                "content": "Please open the Calculator app on my Mac."
            }
        ],
        "tools": schemas,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 256}
    }

    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        res = json.loads(response.read().decode("utf-8"))
    
    msg = res.get("message", {})
    tool_calls = msg.get("tool_calls", [])
    print(f"   Tool calls returned by qwen3:14b: {json.dumps(tool_calls, indent=2)}")
    assert len(tool_calls) > 0, f"Expected tool_calls, got: {msg}"
    
    first_call = tool_calls[0].get("function", {})
    fn_name = first_call.get("name")
    fn_args = first_call.get("arguments", {})
    print(f"   Parsed Function Name: {fn_name}")
    print(f"   Parsed Arguments:     {fn_args}")
    assert fn_name == "open_app", f"Expected open_app, got {fn_name}"
    print("   -> Tool call successfully received and parsed!")

if __name__ == "__main__":
    test_ollama_tags()
    test_basic_chat()
    test_tool_calling()
    print("\nALL PRE-FLIGHT CHECKS PASSED!")
