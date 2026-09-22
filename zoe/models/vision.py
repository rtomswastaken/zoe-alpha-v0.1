"""Local multimodal vision model abstractions and Ollama vision implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
from zoe.macos.logger import zoe_logger


@dataclass
class VisionTargetResult:
    """Structured location result for a target UI element identified by local vision."""
    found: bool
    target: str
    x: Optional[float] = None
    y: Optional[float] = None
    confidence: float = 0.0
    box: Optional[List[float]] = None
    normalized: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VisionAnalysisResult:
    """Structured analysis or description of visible UI state."""
    description: str
    raw: Dict[str, Any] = field(default_factory=dict)


class VisionModel(ABC):
    """Abstract interface for local computer vision engines."""

    @abstractmethod
    def locate(
        self,
        image_b64: str,
        target: str,
        confidence_threshold: Optional[float] = None,
    ) -> VisionTargetResult:
        """Locate target element in image and return structured coordinates and confidence."""
        pass

    @abstractmethod
    def analyze(self, image_b64: str, prompt: str) -> VisionAnalysisResult:
        """Inspect and describe visible screen or window state."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if local vision engine and model are available."""
        pass

    @abstractmethod
    def model_info(self) -> Dict[str, Any]:
        """Return provider and local privacy metadata."""
        pass


class OllamaVisionModel(VisionModel):
    """
    100% local vision engine running through Ollama.
    Communicates via /api/chat with images parameter.
    Zero external APIs or telemetry.
    """

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11434",
        model_name: str = "minicpm-v",
        timeout: float = 90.0,
        default_confidence_threshold: float = 0.75,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self.default_confidence_threshold = default_confidence_threshold

    def is_available(self) -> bool:
        """Check if Ollama daemon is reachable and model is installed."""
        try:
            url = f"{self.endpoint}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as response:
                data = json.loads(response.read().decode("utf-8"))

            available_models = [m.get("name", "") for m in data.get("models", [])]
            clean_target = self.model_name.lower().strip()
            for m in available_models:
                m_clean = m.lower()
                if clean_target == m_clean or clean_target in m_clean:
                    return True
            return False
        except Exception:
            return False

    def model_info(self) -> Dict[str, Any]:
        available = self.is_available()
        return {
            "provider": "Ollama",
            "model": self.model_name,
            "endpoint": self.endpoint,
            "status": "AVAILABLE" if available else "UNAVAILABLE",
            "inference": "LOCAL",
            "screenshots": "LOCAL",
            "network_vision": "DISABLED",
        }

    def locate(
        self,
        image_b64: str,
        target: str,
        confidence_threshold: Optional[float] = None,
    ) -> VisionTargetResult:
        """
        Detect target UI element in base64 image and return structured pixel coordinates.
        Requires confidence >= threshold (default 0.75).
        """
        threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else self.default_confidence_threshold
        )

        prompt = (
            f"You are a computer vision UI grounder. Analyze this screenshot and locate: '{target}'.\n"
            "Return ONLY a single valid JSON object with no explanation, markdown formatting, or thinking:\n"
            "If the element is visible on the screen:\n"
            '{"found": true, "target": "' + target + '", "x": <center X pixel in this image>, "y": <center Y pixel in this image>, "confidence": <float 0.0 to 1.0>}\n'
            "If the element is NOT clearly visible:\n"
            '{"found": false, "target": "' + target + '", "confidence": <float 0.0 to 0.5>}'
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 256},
        }

        try:
            req = urllib.request.Request(
                f"{self.endpoint}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            zoe_logger.log_action("VISION_LOCATE_ERROR", error=str(e), target=target)
            return VisionTargetResult(found=False, target=target, confidence=0.0, raw={"error": str(e)})

        content = raw_data.get("message", {}).get("content", "")
        parsed = self._extract_json_dict(content)

        if not parsed:
            return VisionTargetResult(found=False, target=target, confidence=0.0, raw=raw_data)

        found = bool(parsed.get("found", False))
        conf = float(parsed.get("confidence", 0.0))
        x = float(parsed["x"]) if "x" in parsed and parsed["x"] is not None else None
        y = float(parsed["y"]) if "y" in parsed and parsed["y"] is not None else None

        # Enforce confidence threshold
        if found and conf >= threshold and x is not None and y is not None:
            return VisionTargetResult(
                found=True,
                target=target,
                x=x,
                y=y,
                confidence=conf,
                box=parsed.get("box"),
                normalized=bool(parsed.get("normalized", False)),
                raw=raw_data,
            )
        else:
            return VisionTargetResult(
                found=False,
                target=target,
                x=x,
                y=y,
                confidence=conf,
                raw=raw_data,
            )

    def analyze(self, image_b64: str, prompt: str) -> VisionAnalysisResult:
        """Inspect and describe visible screen or window state."""
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 512},
        }

        try:
            req = urllib.request.Request(
                f"{self.endpoint}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            zoe_logger.log_action("VISION_ANALYZE_ERROR", error=str(e))
            return VisionAnalysisResult(description=f"Vision inspection failed: {str(e)}", raw={"error": str(e)})

        content = raw_data.get("message", {}).get("content", "").strip()
        return VisionAnalysisResult(description=content, raw=raw_data)

    def _extract_json_dict(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON dictionary from raw model text output."""
        try:
            return json.loads(text.strip())
        except Exception:
            pass

        # Match markdown block ```json ... ```
        pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Match raw {...}
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except Exception:
                pass

        return None
