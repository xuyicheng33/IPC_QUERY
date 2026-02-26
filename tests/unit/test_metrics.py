"""
metrics 模块测试
"""

from __future__ import annotations

from ipc_query.constants import METRICS_HISTOGRAM_WINDOW
from ipc_query.utils.metrics import Histogram, Metrics


def test_histogram_uses_bounded_window() -> None:
    hist = Histogram()
    total = METRICS_HISTOGRAM_WINDOW + 25
    for i in range(total):
        hist.observe(float(i))

    stats = hist.get_stats()
    assert stats["count"] == METRICS_HISTOGRAM_WINDOW
    assert stats["max"] == float(total - 1)
    assert stats["min"] == float(total - METRICS_HISTOGRAM_WINDOW)


def test_metrics_export_and_reset() -> None:
    m = Metrics()
    m.record_search(12.5, cache_hit=True)
    m.record_search(3.5, cache_hit=False)
    m.record_render(8.0)
    m.record_error("db")

    exported = m.export()
    counters = exported["counters"]
    assert counters["search_requests_total"] == 2
    assert counters["cache_hits"] == 1
    assert counters["cache_misses"] == 1
    assert counters["render_requests_total"] == 1
    assert counters["errors_db"] == 1
    assert exported["histograms"]["search_latency_ms"]["count"] == 2

    m.reset()
    after_reset = m.export()
    assert after_reset["histograms"]["search_latency_ms"]["count"] == 0
    assert after_reset["histograms"]["render_latency_ms"]["count"] == 0
