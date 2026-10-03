"""Lightweight performance timing and telemetry utilities for StudyRAG V2."""

import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("StudyRAG.Performance")


class PerformanceTracker:
    """Tracks latency metrics across the RAG execution pipeline."""

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or str(int(time.time() * 1000))
        self.start_time = time.perf_counter()
        self.metrics: Dict[str, float] = {}
        self.metadata: Dict[str, Any] = {}
        self._current_timers: Dict[str, float] = {}

    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        self._current_timers[name] = time.perf_counter()

    def stop_timer(self, name: str) -> float:
        """Stop a named timer and record elapsed seconds."""
        if name in self._current_timers:
            elapsed = time.perf_counter() - self._current_timers.pop(name)
            self.metrics[name] = round(elapsed, 4)
            return elapsed
        return 0.0

    def record_metric(self, name: str, value: float) -> None:
        """Record an explicit metric value."""
        self.metrics[name] = round(value, 4)

    def record_meta(self, key: str, value: Any) -> None:
        """Record context metadata (e.g. chunk count, char count)."""
        self.metadata[key] = value

    def get_total_elapsed(self) -> float:
        """Get total elapsed time since tracker creation."""
        return round(time.perf_counter() - self.start_time, 4)

    def log_summary(self) -> None:
        """Output clean structured performance log."""
        total = self.get_total_elapsed()
        self.metrics["total_request"] = total

        parts = [f"{k}={v}s" for k, v in self.metrics.items()]
        meta_parts = [f"{k}={v}" for k, v in self.metadata.items()]

        log_line = "[PERF] " + " | ".join(parts)
        if meta_parts:
            log_line += " | Meta: " + ", ".join(meta_parts)

        logger.info(log_line)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "request_id": self.request_id,
            "total_time_seconds": self.get_total_elapsed(),
            "metrics": self.metrics,
            "metadata": self.metadata,
        }
