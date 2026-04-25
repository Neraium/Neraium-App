from __future__ import annotations

import argparse
import csv
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from neraium_core.live_runner import process_live_frame
from neraium_core.stock_market_adapter import build_stock_frame
from neraium_core.trading_signals import IntradaySignalPolicy, build_signal_decision


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MockLiveStream:
    """Read historical rows and emit one-by-one with delay to mimic live streaming."""

    def __init__(self, csv_path: str, delay_seconds: float = 0.25, loop_forever: bool = True) -> None:
        self.csv_path = Path(csv_path)
        self.delay_seconds = max(0.0, delay_seconds)
        self.loop_forever = loop_forever

    def __iter__(self) -> Iterator[Bar]:
        while True:
            emitted = False
            with self.csv_path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    bar = self._parse_row(row)
                    if bar is None:
                        continue
                    emitted = True
                    yield bar
                    if self.delay_seconds:
                        time.sleep(self.delay_seconds)
            if not self.loop_forever or not emitted:
                break

    @staticmethod
    def _parse_row(row: dict[str, str]) -> Bar | None:
        try:
            raw_ts = str(row["timestamp"]).strip()
            if raw_ts.endswith("Z"):
                raw_ts = raw_ts[:-1] + "+00:00"
            ts = datetime.fromisoformat(raw_ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return Bar(
                timestamp=ts,
                ticker=str(row["ticker"]).upper().strip(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0) or 0.0),
            )
        except (KeyError, TypeError, ValueError):
            return None


class RollingBars:
    """Maintain per-ticker rolling 1m bars and derived 5m bars."""

    def __init__(self, maxlen: int = 600) -> None:
        self._bars_1m: dict[str, deque[Bar]] = defaultdict(lambda: deque(maxlen=maxlen))
        self._bars_5m: dict[str, deque[Bar]] = defaultdict(lambda: deque(maxlen=maxlen))

    def update(self, bar: Bar) -> tuple[list[Bar], list[Bar]]:
        bars_1m = self._bars_1m[bar.ticker]
        bars_1m.append(bar)

        bucket_ts = bar.timestamp.replace(second=0, microsecond=0)
        minute = bucket_ts.minute - (bucket_ts.minute % 5)
        bucket_start = bucket_ts.replace(minute=minute)

        bars_5m = self._bars_5m[bar.ticker]
        if not bars_5m or bars_5m[-1].timestamp != bucket_start:
            bars_5m.append(
                Bar(
                    timestamp=bucket_start,
                    ticker=bar.ticker,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
            )
        else:
            prev = bars_5m[-1]
            bars_5m[-1] = Bar(
                timestamp=prev.timestamp,
                ticker=prev.ticker,
                open=prev.open,
                high=max(prev.high, bar.high),
                low=min(prev.low, bar.low),
                close=bar.close,
                volume=prev.volume + bar.volume,
            )

        return list(bars_1m), list(bars_5m)


class _FallbackStructuralEngine:
    def __init__(self, baseline_window: int = 40, recent_window: int = 12) -> None:
        self.baseline_window = baseline_window
        self.recent_window = recent_window
        self._last_value: float | None = None

    def process_frame(self, frame: dict[str, Any]) -> dict[str, Any]:
        sensors = frame.get("sensor_values", {})
        current = sensors.get("close", sensors.get("value", 0.0))
        change = 0.0 if self._last_value in {None, 0.0} else (float(current) - float(self._last_value)) / float(self._last_value)
        self._last_value = float(current)

        score = min(3.5, abs(change) * 100.0)
        state = "ALERT" if score >= 3.0 else "WATCH" if score >= 2.0 else "NORMAL"
        return {
            "classification": state,
            "drift_state": state,
            "structural_drift_score": score,
            "latest_instability": score,
            "system_health": max(0.0, 100.0 - score * 20.0),
            "evidence_confidence": 0.75,
            "explanation_text": f"{state} regime from close-move score={score:.2f}",
        }


class NeraiumLiveRunner:
    """Local-only live runner (no broker, no external APIs)."""

    def __init__(self, warmup_bars: int = 5) -> None:
        try:
            from neraium_core.alignment import StructuralEngine  # type: ignore
        except ModuleNotFoundError:
            StructuralEngine = _FallbackStructuralEngine

        self._engines: dict[str, Any] = defaultdict(lambda: StructuralEngine())
        self._last_emitted: dict[str, dict[str, Any]] = {}
        self._bars_seen: dict[str, int] = defaultdict(int)
        self._rolling = RollingBars()
        self._policy = IntradaySignalPolicy(warmup_bars=warmup_bars, min_confidence=0.2, cooldown_seconds=0)

    def on_bar(self, bar: Bar) -> dict[str, Any] | None:
        bars_1m, bars_5m = self._rolling.update(bar)
        frame = build_stock_frame(timestamp=float(bar.timestamp.timestamp()), ticker=bar.ticker, row_dict=bar.__dict__)
        result = process_live_frame(self._engines[bar.ticker], frame)

        self._bars_seen[bar.ticker] += 1
        decision = build_signal_decision(
            output=result,
            ticker=bar.ticker,
            timestamp=bar.timestamp,
            policy=self._policy,
            previous=self._last_emitted.get(bar.ticker),
            bars_seen=self._bars_seen[bar.ticker],
        )

        signal = str(decision["trading_signal"]).upper()
        action_permission = "ALLOW" if signal in {"BUY", "SELL", "EXIT", "REDUCE"} else "ABSTAIN"
        best_action = signal if signal != "WARMUP" else "HOLD"
        fragility = min(1.0, float(decision["latest_instability"]) / 3.5)

        out = {
            "timestamp": bar.timestamp.isoformat(),
            "ticker": bar.ticker,
            "action_permission": action_permission,
            "best_action": best_action,
            "confidence": float(decision["confidence"]),
            "fragility": round(fragility, 4),
            "one_line_reason": f"{decision['reason']} | bars_1m={len(bars_1m)} bars_5m={len(bars_5m)}",
        }

        self._last_emitted[bar.ticker] = {
            "timestamp": bar.timestamp,
            "trading_signal": signal,
            "state": decision["state"],
            "structural_drift_score": decision["structural_drift_score"],
        }
        return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Neraium live mode from local CSV/mock stream only.")
    parser.add_argument("--csv", default="data/sample_market_data.csv", help="CSV source for mock live feed")
    parser.add_argument("--delay", type=float, default=0.25, help="Seconds between rows")
    parser.add_argument("--warmup-bars", type=int, default=5, help="Bars required before non-warmup actions")
    parser.add_argument("--max-events", type=int, default=0, help="Optional cap for smoke runs (0 = infinite when loop mode is enabled)")
    parser.add_argument("--loop", dest="loop", action="store_true", default=True, help="Continuously replay CSV forever (default)")
    parser.add_argument("--no-loop", dest="loop", action="store_false", help="Run one pass through the CSV and stop")
    return parser.parse_args()


def run_live(csv_path: str, delay: float, warmup_bars: int, max_events: int = 0, loop: bool = True) -> None:
    stream = MockLiveStream(csv_path=csv_path, delay_seconds=delay, loop_forever=loop)
    runner = NeraiumLiveRunner(warmup_bars=warmup_bars)

    seen = 0
    for bar in stream:
        output = runner.on_bar(bar)
        if output is None:
            continue
        print(
            " | ".join(
                [
                    output["timestamp"],
                    output["ticker"],
                    f"action_permission={output['action_permission']}",
                    f"best_action={output['best_action']}",
                    f"confidence={output['confidence']:.2f}",
                    f"fragility={output['fragility']:.2f}",
                    f"one_line_reason={output['one_line_reason']}",
                ]
            )
        )
        seen += 1
        if max_events and seen >= max_events:
            break


def main() -> None:
    args = parse_args()
    run_live(
        csv_path=args.csv,
        delay=args.delay,
        warmup_bars=args.warmup_bars,
        max_events=args.max_events,
        loop=args.loop,
    )


if __name__ == "__main__":
    main()
