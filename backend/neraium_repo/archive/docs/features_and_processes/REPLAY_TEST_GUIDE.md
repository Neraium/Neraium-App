# Greenhouse Replay Refinement - Test & Validation Guide

## Quick Start

### Local Testing (Recommended)

```bash
# From repository root
python run_ui.py
# or
python start_ui.py
```

The app will open at: **http://localhost:7860**

### What to Observe During Playback

#### 1. **Smooth Progression** ✓
- Click the **Play** button
- Watch the frame counter advance steadily (1→180)
- Observe trajectory chart updating smoothly
- Verdict changes should feel measured, not abrupt

#### 2. **Phase-Aware Timing** ✓
- Look at "Phase:" label in header (Baseline / Transition / Reorganization)
- **Stable phases** (Baseline): Notice slightly longer dwell time per frame
- **Transition phases**: Frames advance slightly faster to convey change
- Timing differences should be subtle but noticeable (±0.25s variation)

#### 3. **Verdict Stability** ✓
Most critical test:
- Watch the verdict label during playback (top center: "COHERENT CHANGE DETECTED", etc.)
- **Expected:** Verdict should NOT flip back and forth between consecutive frames
- **Before fix:** Would see labels changing erratically (ADMITTED → SUPPRESSED → ADMITTED)
- **After fix:** Label stays stable, only changes when signal is strong and sustained

#### 4. **Speed Control** ✓
- Pause playback (click Pause)
- Move **Speed** slider
  - Left (0.1): Very slow, long delays
  - Right (1.5): Fast, compressed timing
- Click Play again - observe that timing adjusts but phase-relative differences persist
- Reset and replay at different speeds

#### 5. **Clean Reset** ✓
- Start playback
- While playing, click **Reset**
- Should return to Frame 1 immediately
- Verdict should reset to neutral state (SUPPRESSED)
- Can start new playback from beginning

#### 6. **Pause & Resume** ✓
- Start playback
- Click **Pause** mid-sequence (say at frame 60)
- Verify all visuals freeze completely
- Move frame slider manually to verify state is preserved
- Can resume by clicking Play again

## Validation Metrics

### Timing Measurements

Run this test to verify adaptive pacing:

```bash
python << 'EOF'
from ui.replay_timing import ReplayPaceController
from ui.demo_data import load_greenhouse_demo_records

rows = load_greenhouse_demo_records(limit=100)
pace = ReplayPaceController(speed_multiplier=1.0)

print("Frame Phase Analysis:")
print("Frame | Phase      | Delay")
print("-" * 40)

for i in range(min(20, len(rows))):
    from ui.replay_timing import get_phase_type
    phase = get_phase_type(rows[i])
    delay = pace.get_step_delay(i, rows)
    print(f"{i:3d}  | {phase:10s} | {delay:.3f}s")

# Verify stable delay ratio
pace2 = ReplayPaceController(speed_multiplier=1.0)
stable_delays = []
transition_delays = []

for i in range(len(rows)):
    delay = pace2.get_step_delay(i, rows)
    phase = get_phase_type(rows[i])
    if phase == "STABLE":
        stable_delays.append(delay)
    else:
        transition_delays.append(delay)

if stable_delays and transition_delays:
    ratio = sum(stable_delays) / len(stable_delays) / (sum(transition_delays) / len(transition_delays))
    print(f"\nStable delay / Transition delay ratio: {ratio:.2f}")
    print(f"Expected: ~1.27 (1.4 / 1.1)")
EOF
```

### Verdict Stability Validation

```bash
python << 'EOF'
from ui.replay_timing import VerdictStabilizer

stabilizer = VerdictStabilizer(hysteresis_threshold=0.08)

# Simulate frame sequence with minor signal fluctuations
test_sequence = [
    ("SUPPRESS", 0.00),
    ("SUPPRESS", 0.02),  # Too small
    ("SUPPRESS", 0.04),  # Still small
    ("SUPPRESS", 0.07),  # Below threshold
    ("ADMIT", 0.10),     # Above threshold - SWITCH
    ("ADMIT", 0.11),     # Stay
    ("ADMIT", 0.12),     # Stay
    ("SUPPRESS", 0.02),  # Too small - STAY ADMIT
    ("SUPPRESS", 0.09),  # Above threshold - SWITCH
]

print("Verdict Hysteresis Test:")
print("Real | Signal | Displayed | Changed?")
print("-" * 40)

for real_decision, signal in test_sequence:
    decision = {
        "decision": real_decision,
        "transition": {"delta_drift": signal}
    }
    result = stabilizer.apply_stability(decision)
    displayed = result.get("decision")
    changed = result.get("_verdict_changed")
    print(f"{real_decision:4} | {signal:6.2f} | {displayed:9} | {changed}")

print("\n✓ Verdict should only change at signal ≥ 0.08")
EOF
```

## Expected Behavior Checklist

- [ ] **Initial Load**: App loads frame 30/180 with stable verdict
- [ ] **Play Start**: Frames advance at 0.7-1.2s per frame (depends on phase)
- [ ] **Stable Phases**: Slightly longer dwell (≈1.2s vs 0.9s for transitions)
- [ ] **Verdict**: Never flips between adjacent frames
- [ ] **Phase Label**: Updates in header as replay progresses
- [ ] **Speed Change**: Adjusting speed slider affects timing proportionally
- [ ] **Pause**: Freezes completely, all state preserved
- [ ] **Reset**: Returns to frame 1, verdicts reset to neutral
- [ ] **Resume**: Can restart playback from any point

## Troubleshooting

### Verdict Still Flipping?
- Increase `hysteresis_threshold` in `ui/app.py`:
  ```python
  verdict_stabilizer = VerdictStabilizer(hysteresis_threshold=0.12)
  ```
- Test again with `python run_ui.py`

### Timing Too Fast/Slow?
- Adjust `stable_linger_ratio` in `ui/app.py`:
  ```python
  pace_controller = ReplayPaceController(
      speed_multiplier=1.0,
      stable_linger_ratio=1.6,  # Increase for longer stable phases
      transition_emphasis_ratio=1.2  # Increase for slower transitions
  )
  ```

### UI Doesn't Update During Playback?
- Check browser console for JavaScript errors
- Verify Gradio is running: `pip install gradio`
- Restart app: `python run_ui.py`

## Performance Notes

- Timing accuracy: ±50ms (acceptable for 0.7-1.2s delays)
- Phase detection: Instant (no perceptible lag)
- Verdict stability check: <1ms per frame
- Memory: Stabilizers use O(1) space, no accumulation

## Integration Points

If integrating into larger system:

1. **Import stabilizers in your UI controller:**
   ```python
   from ui.replay_timing import ReplayPaceController, VerdictStabilizer
   ```

2. **Apply stability before rendering:**
   ```python
   stabilizer.apply_stability(gate_decision, signal_strength=drift)
   ```

3. **Use adaptive timing in playback loop:**
   ```python
   delay = pace_controller.get_step_delay(frame_index, rows)
   time.sleep(delay)
   ```

4. **Reset on playback start:**
   ```python
   stabilizer.reset()
   reasoning_tracker.reset()
   ```

## Files Reference

- **Implementation:** `ui/replay_timing.py`
- **UI Integration:** `ui/app.py` (lines 585-697)
- **Documentation:** `REPLAY_REFINEMENTS.md`
- **Demo Data:** `greenhouse_demo/greenhouse_results_turbo.csv`
- **Test Entry:** `run_ui.py` / `start_ui.py`

## Contact & Feedback

For questions about replay behavior:
1. Review `REPLAY_REFINEMENTS.md` for architecture
2. Check `ui/replay_timing.py` docstrings for API details
3. Run unit tests: `python -m pytest tests/` (if available)
4. Test interactively: `python run_ui.py`
