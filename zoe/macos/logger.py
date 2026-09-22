"""Local action logger for Zoe."""

from datetime import datetime
from pathlib import Path
import threading
from typing import Any, Dict, List
from zoe.config import get_config


class ZoeLogger:
    """Thread-safe local action logger that writes structured timestamps and key-values."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: List[Dict[str, Any]] = []
        self._config = get_config()
        self._log_file_path: Path | None = None
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        if self._config.logging.enabled and self._config.logging.file_path:
            p = Path(self._config.logging.file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._log_file_path = p

    def log_action(self, action: str, **kwargs: Any) -> str:
        """
        Log an action locally with timestamp and key-values.
        Example output: [22:31:04] MOVE_CURSOR x=842 y=611 duration=0.42
        """
        now = datetime.now()
        timestamp_str = now.strftime("%H:%M:%S")

        # Mask sensitive text if enabled
        safe_kwargs: Dict[str, Any] = {}
        for k, v in kwargs.items():
            if self._config.logging.mask_sensitive and k.lower() in ("text", "password", "secret", "typed_text"):
                safe_kwargs["length"] = len(str(v))
            else:
                safe_kwargs[k] = v

        kv_parts = [f"{k}={v}" for k, v in safe_kwargs.items()]
        kv_str = (" " + " ".join(kv_parts)) if kv_parts else ""
        formatted_line = f"[{timestamp_str}] {action.upper()}{kv_str}"

        with self._lock:
            self._history.append({
                "timestamp": now.isoformat(),
                "time_str": timestamp_str,
                "action": action.upper(),
                "details": safe_kwargs,
                "line": formatted_line
            })
            if len(self._history) > 1000:
                self._history.pop(0)

            if self._config.logging.enabled:
                if self._log_file_path:
                    try:
                        with open(self._log_file_path, "a", encoding="utf-8") as f:
                            f.write(formatted_line + "\n")
                    except Exception:
                        pass

                if self._config.logging.console_output:
                    print(formatted_line)

        return formatted_line

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history[-limit:])

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()


zoe_logger = ZoeLogger()
