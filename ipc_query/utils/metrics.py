"""
性能指标模块

提供简单的性能指标收集功能。
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from ..constants import METRICS_HISTOGRAM_WINDOW


def _new_histogram_values() -> deque[float]:
    return deque(maxlen=max(1, int(METRICS_HISTOGRAM_WINDOW)))


@dataclass
class Counter:
    """计数器指标"""

    value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def increment(self, delta: int = 1) -> None:
        with self._lock:
            self.value += delta

    def get(self) -> int:
        with self._lock:
            return self.value

    def reset(self) -> None:
        with self._lock:
            self.value = 0


@dataclass
class Histogram:
    """直方图指标"""

    values: deque[float] = field(default_factory=_new_histogram_values)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def observe(self, value: float) -> None:
        with self._lock:
            self.values.append(value)

    def get_stats(self) -> dict[str, float]:
        with self._lock:
            if not self.values:
                return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0, "p99": 0}

            sorted_values = sorted(list(self.values))
            count = len(sorted_values)
            total = sum(sorted_values)
            avg = total / count
            p99_index = int(count * 0.99)

            return {
                "count": count,
                "sum": total,
                "avg": avg,
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "p99": sorted_values[min(p99_index, count - 1)],
            }

    def reset(self) -> None:
        with self._lock:
            self.values.clear()


@dataclass
class Gauge:
    """仪表指标"""

    value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set(self, value: float) -> None:
        with self._lock:
            self.value = value

    def get(self) -> float:
        with self._lock:
            return self.value


class Metrics:
    """
    指标收集器

    收集和暴露系统性能指标。
    """

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = defaultdict(Counter)
        self._histograms: dict[str, Histogram] = defaultdict(Histogram)
        self._gauges: dict[str, Gauge] = defaultdict(Gauge)
        self._start_time: float = time.time()

    # === 计数器操作 ===

    def counter_increment(self, name: str, delta: int = 1) -> None:
        """增加计数器"""
        self._counters[name].increment(delta)

    def counter_get(self, name: str) -> int:
        """获取计数器值"""
        return self._counters[name].get()

    # === 直方图操作 ===

    def histogram_observe(self, name: str, value: float) -> None:
        """记录直方图值"""
        self._histograms[name].observe(value)

    def histogram_get_stats(self, name: str) -> dict[str, float]:
        """获取直方图统计"""
        return self._histograms[name].get_stats()

    # === 仪表操作 ===

    def gauge_set(self, name: str, value: float) -> None:
        """设置仪表值"""
        self._gauges[name].set(value)

    def gauge_get(self, name: str) -> float:
        """获取仪表值"""
        return self._gauges[name].get()

    # === 便捷方法 ===

    def time_it(self, name: str) -> "TimerContext":
        """计时上下文管理器"""
        return TimerContext(self, name)

    def record_search(self, duration_ms: float, cache_hit: bool = False) -> None:
        """记录搜索指标"""
        self.counter_increment("search_requests_total")
        self.histogram_observe("search_latency_ms", duration_ms)
        if cache_hit:
            self.counter_increment("cache_hits")
        else:
            self.counter_increment("cache_misses")

    def record_render(self, duration_ms: float) -> None:
        """记录渲染指标"""
        self.counter_increment("render_requests_total")
        self.histogram_observe("render_latency_ms", duration_ms)

    def record_error(self, error_type: str) -> None:
        """记录错误"""
        self.counter_increment(f"errors_{error_type}")

    # === 导出 ===

    def export(self) -> dict[str, Any]:
        """导出所有指标"""
        uptime = time.time() - self._start_time

        counters = {name: counter.get() for name, counter in self._counters.items()}
        gauges = {name: gauge.get() for name, gauge in self._gauges.items()}
        histograms = {}
        for name, hist in self._histograms.items():
            histograms[name] = hist.get_stats()

        return {
            "uptime_seconds": uptime,
            "counters": counters,
            "gauges": gauges,
            "histograms": histograms,
        }

    def reset(self) -> None:
        """重置所有指标"""
        for counter in self._counters.values():
            counter.reset()
        for hist in self._histograms.values():
            hist.reset()


class TimerContext:
    """计时上下文管理器"""

    def __init__(self, metrics: Metrics, name: str):
        self.metrics = metrics
        self.name = name
        self.start_time: float = 0.0

    def __enter__(self) -> "TimerContext":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        self.metrics.histogram_observe(self.name, duration_ms)


# 全局指标实例
metrics = Metrics()
