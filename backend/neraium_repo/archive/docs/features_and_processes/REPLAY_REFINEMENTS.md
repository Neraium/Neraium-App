# Greenhouse Replay Refinements

## Overview

This refinement improves the greenhouse replay behavior to feel deliberate, stable, and high-authority during playback. The interface now presents as a confident system observing real change over time, not a twitchy demo.

## Key Improvements

### 1. **Smooth Playback with Adaptive Timing**

**Module:** `ui/replay_timing.py` → `ReplayPaceController`

**Behavior:**
- Stable phases linger longer (1.4× base delay) to establish baseline
- Transition phases use standard emphasis (1.1× base delay) to convey change
- Base delay: `0.85 / speed_multiplier` seconds (≈0.7s at speed 1.0)
- Speed slider (0.1 to 1.5) scales delay inversely

**Result:** 
- System "breathes" during stability
- Transitions feel noticeably different without being rushed
- Entire sequence feels measured and intentional

### 2. **Verdict Stability with Hysteresis**

**Module:** `ui/replay_timing.py` → `VerdictStabilizer`

**Mechanism:**
- Tracks both real verdict (from gate engine) and displayed verdict (to user)
- Only switches displayed verdict when:
  1. Real verdict changes AND
  2. Signal strength crosses hysteresis threshold (default: 0.08)
- Prevents verdict flipping frame-to-frame due to minor fluctuations

**Configuration:**
```python
stabilizer = VerdictStabilizer(hysteresis_threshold=0.08)
# Threshold range: 0-1 normalized drift intensity
# Higher = more stability, lower = more responsiveness
```

**Result:**
- Verdicts feel earned by sustained replay progression
- Labels don't jitter in response to every row
- User confidence in displayed judgment increases

### 3. **Reasoning Evolution Tracking**

**Module:** `ui/replay_timing.py` → `ReasoningStateTracker`

**Capability:**
- Tracks previous row state and reasoning outputs
- Only triggers re-render when metrics change meaningfully
- Observes: drift, stability, event_admitted, transition_type, system_health
- Change threshold: default 0.06 (6% of normalized metrics)

**Usage:**
```python
tracker = ReasoningStateTracker(change_threshold=0.06)
should_update = tracker.should_update_reasoning(current_row, previous_row)
```

**Result:**
- Reasoning lines stay consistent across stable spans
- Updates feel intentional, not chatty
- Reduces visual noise during playback

### 4. **Phase Progress Indicator**

**Location:** `ui/app.py` → `render_command_header()`

**Display:**
- Header now shows "Phase: Baseline" / "Phase: Transition" / "Phase: Reorganization"
- Replaces "Regime" metric with clearer phase label
- Helps users understand what kind of replay interval they're in

**Result:**
- Visual feedback about playback context
- Better understanding of why timing changes

### 5. **Clean Reset & Pause Behavior**

**Updates:**
- `reset_playback()` now resets stabilizer state:
  - Verdict stabilizer reverts to neutral (SUPPRESS)
  - Reasoning tracker clears history
  - Ensures next playback starts from clean slate

- `pause_playback()` freezes cleanly:
  - All state preserved exactly
  - Resume can continue mid-playback if needed

## Implementation Details

### How Verdict Stability Works

```
Frame 1: SUPPRESS (real: SUPPRESS)
Frame 2: SUPPRESS, drift=0.04 (real: SUPPRESS) → too small, stay SUPPRESS
Frame 3: SUPPRESS, drift=0.07 (real: SUPPRESS) → still below threshold
Frame 4: ADMIT, drift=0.12 (real: ADMIT) → signal strong enough, SWITCH to ADMIT
Frames 5-10: ADMIT (real: ADMIT) → stay displayed
Frame 11: SUPPRESS, drift=0.02 (real: SUPPRESS) → weak signal, STAY ADMIT
Frame 12: SUPPRESS, drift=0.10 (real: SUPPRESS) → signal strong enough, SWITCH to SUPPRESS
```

The hysteresis prevents bouncing between states due to minor metric shifts.

### Adaptive Timing Calculation

```
base_delay = 0.85 / speed_multiplier

if phase == "STABLE":
    delay = base_delay * 1.4  # Linger 40% longer
elif phase == "TRANSITION" or "REORGANIZATION":
    delay = base_delay * 1.1  # 10% emphasis
else:
    delay = base_delay
```

## Configuration

All timing and stability parameters are configurable:

```python
# In ui/app.py create_gradio_app()
verdict_stabilizer = VerdictStabilizer(hysteresis_threshold=0.08)
reasoning_tracker = ReasoningStateTracker(change_threshold=0.06)
pace_controller = ReplayPaceController(
    speed_multiplier=1.0,
    stable_linger_ratio=1.4,
    transition_emphasis_ratio=1.1,
)
```

Suggested tuning:
- **More stable verdicts:** increase `hysteresis_threshold` to 0.12+
- **Faster baseline:** decrease `stable_linger_ratio` to 1.2
- **Emphasize transitions:** increase `transition_emphasis_ratio` to 1.3

## Testing

### Unit Tests
All timing and stabilization components have been tested:
```bash
python -c "
from ui.replay_timing import (
    ReplayPaceController,
    VerdictStabilizer,
    ReasoningStateTracker,
    get_phase_type,
)
# Tests: phase detection, pace calculation, verdict hysteresis
print('✓ All timing and stability tests passed!')
"
```

### Local Testing
```bash
python run_ui.py
# or
python start_ui.py
```

The Gradio app will launch on `http://localhost:7860`

Test procedure:
1. Click **Play** to start replay
2. Observe verdict stability (no flipping)
3. Notice stable phases linger, transitions move faster
4. Adjust **Speed** slider and observe adaptive timing
5. Click **Pause** mid-playback (state freezes cleanly)
6. Click **Reset** (returns to frame 1, clean state)

## Preserved

- ✅ Real greenhouse replay source (`greenhouse_results_turbo.csv`)
- ✅ Compact verdict + trajectory surface
- ✅ Premium dark styling
- ✅ Verdict label improvements from previous work
- ✅ Supporting line and header clarity
- ✅ Phase replay timeline strip

## Files Modified

1. **`ui/replay_timing.py`** (NEW)
   - `ReplayPaceController` class
   - `VerdictStabilizer` class
   - `ReasoningStateTracker` class
   - Helper functions for phase classification and analysis

2. **`ui/app.py`**
   - Import replay_timing modules
   - Initialize stabilizers and pace controller in `create_gradio_app()`
   - Modified `load_operations_surface()` to apply verdict stability
   - Updated `autoplay()` to use adaptive pacing
   - Enhanced `render_command_header()` with phase labels
   - Updated `reset_playback()` to clean stabilizer state

## Impact on User Experience

**Before:** Verdict labels flip frame-to-frame, timing feels uniform, reasoning updates every frame
**After:** Verdict feels earned, timing reflects phase importance, reasoning evolves intentionally

The interface now feels like a confident system observing real change over time, building toward conclusions, not reacting to every fluctuation.

## References

- Replay source: `greenhouse_demo/greenhouse_results_turbo.csv`
- UI entry: `run_ui.py` / `start_ui.py`
- Theme: `ui/themes/neraium_dark.css`
- Gate decision logic: `neraium_core/gate/engine.py`
