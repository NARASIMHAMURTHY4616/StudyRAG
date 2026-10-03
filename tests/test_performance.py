"""Unit tests for PerformanceTracker diagnostic module."""

import time
from core.performance import PerformanceTracker


def test_performance_tracker_timings():
    tracker = PerformanceTracker(request_id="test_req_01")
    tracker.start_timer("test_op")
    time.sleep(0.05)
    elapsed = tracker.stop_timer("test_op")

    assert elapsed >= 0.04
    assert "test_op" in tracker.metrics
    assert tracker.metrics["test_op"] >= 0.04

    tracker.record_meta("chunks", 4)
    data = tracker.to_dict()

    assert data["request_id"] == "test_req_01"
    assert data["metadata"]["chunks"] == 4
    assert data["total_time_seconds"] >= 0.04
