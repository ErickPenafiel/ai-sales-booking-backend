import os
import time
import json
import logging
import threading
from typing import List, Dict, Any, Callable

import requests

logger = logging.getLogger("app.services.tracing")

LOGS_FOLDER = os.getenv("LOGS_FOLDER", "./logs")
os.makedirs(LOGS_FOLDER, exist_ok=True)
TRACES_FILE = os.path.join(LOGS_FOLDER, "langsmith_traces.jsonl")

# Control whether we attempt to upload traces remotely (may cause 429s if enabled)
REMOTE_ENABLED = os.getenv("LANGSMITH_UPLOAD_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")

try:
    from langsmith import traceable as _langsmith_traceable
except Exception:  # pragma: no cover
    _langsmith_traceable = None


def _make_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            out[str(k)] = _make_json_safe(v)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_make_json_safe(v) for v in value]
    return str(value)


def langsmith_traceable(*, run_type: str = "chain", name: str | None = None) -> Callable:
    """Best-effort traceable decorator. Falls back to no-op if langsmith is unavailable."""

    def _decorator(func: Callable) -> Callable:
        if _langsmith_traceable is None:
            return func

        kwargs: Dict[str, Any] = {"run_type": run_type}
        if name:
            kwargs["name"] = name
        return _langsmith_traceable(**kwargs)(func)

    return _decorator


class TraceCollector:
    def __init__(self):
        self._lock = threading.Lock()
        self._rate_limited_until = 0.0

    def record(self, trace: Dict[str, Any]) -> None:
        """Persist trace locally and optionally try to upload remotely with backoff.

        Always append the trace to the local file (for UI display). Remote upload
        is best-effort and will respect Retry-After / backoff to avoid 429 storms.
        """
        trace_copy = _make_json_safe(dict(trace))
        trace_copy.setdefault("timestamp", time.time())

        try:
            line = json.dumps(trace_copy, ensure_ascii=False)
            with self._lock:
                with open(TRACES_FILE, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception:
            logger.exception("Failed to write local trace")

        if REMOTE_ENABLED and LANGSMITH_ENDPOINT and LANGSMITH_API_KEY:
            threading.Thread(target=self._send_remote, args=(trace_copy,), daemon=True).start()

    def _send_remote(self, trace: Dict[str, Any]) -> None:
        now = time.time()
        if now < self._rate_limited_until:
            logger.debug("Remote traces temporarily suspended until %s", self._rate_limited_until)
            return

        url = LANGSMITH_ENDPOINT.rstrip("/") + "/traces"
        headers = {"Authorization": f"Bearer {LANGSMITH_API_KEY}", "Content-Type": "application/json"}

        max_retries = 3
        backoff = 1.0
        for attempt in range(max_retries):
            try:
                resp = requests.post(url, headers=headers, json=trace, timeout=10)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    try:
                        wait = float(retry_after) if retry_after is not None else backoff * 2
                    except Exception:
                        wait = backoff * 2
                    self._rate_limited_until = time.time() + wait
                    logger.warning("LangSmith remote trace rate limited, pausing uploads for %.1f seconds", wait)
                    return
                resp.raise_for_status()
                logger.debug("LangSmith remote trace uploaded successfully")
                return
            except requests.HTTPError as e:
                logger.debug("LangSmith remote trace failed: %s", e)
            except Exception as e:
                logger.exception("Unexpected error while sending remote trace: %s", e)

            time.sleep(backoff)
            backoff *= 2

    def list_traces(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return last `limit` traces from the local jsonl file."""
        if not os.path.exists(TRACES_FILE):
            return []

        try:
            with open(TRACES_FILE, "r", encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except Exception:
            logger.exception("Failed to read traces file")
            return []

        # take last `limit` lines
        selected = lines[-limit:]
        out: List[Dict[str, Any]] = []
        for ln in selected:
            try:
                out.append(json.loads(ln))
            except Exception:
                logger.debug("Skipping malformed trace line")
        return out


collector = TraceCollector()


def record_trace(payload: Dict[str, Any]) -> None:
    try:
        collector.record(payload)
    except Exception:
        logger.exception("record_trace failed")


def list_traces(limit: int = 100) -> List[Dict[str, Any]]:
    return collector.list_traces(limit)
