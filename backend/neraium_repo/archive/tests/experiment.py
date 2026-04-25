from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from numpy.linalg import lstsq, eigvals

DATA_PATH = Path(__file__).resolve().parent / "train_FD004.txt"

SIGNAL_COLUMNS = ["s_2", "s_3", "s_4", "s_7"]
WINDOW = 20
DEGRADATION_FRACTION = 0.8
EMA_ALPHA = 0.2
CUMULATIVE_N = 30
NUM_UNITS = 100

# false-positive / stability controls
HEALTHY_FRACTION = 0.2
PERSISTENCE = 5
THRESHOLD_STD = 2.0
MIN_FILTERED_HEALTHY_SAMPLES = 10
# =========================
# HYBRID DETECTOR (V4)
# =========================



def _cfg_get(config, key, default):
    if isinstance(config, dict):
        return config.get(key, default)
    if hasattr(config, key):
        value = getattr(config, key)
        return default if value is None else value
    return default


def build_relational_features(data) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        arr = np.asarray(data, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        df = pd.DataFrame(arr)

    if df.columns is None or any(c is None for c in df.columns):
        df.columns = [f"sensor_{i}" for i in range(df.shape[1])]
    else:
        names = []
        for i, c in enumerate(df.columns):
            name = str(c)
            names.append(name if name.strip() else f"sensor_{i}")
        if len(set(names)) != len(names):
            names = [f"sensor_{i}" for i in range(df.shape[1])]
        df.columns = names

    ema = df.ewm(alpha=0.25, adjust=False).mean()
    residual = df - ema
    diff = df.diff()
    rolling_std = df.rolling(window=10, min_periods=1).std()

    first_sensor = df.iloc[:, 0]
    divergence = df.subtract(first_sensor, axis=0)

    ema.columns = [f"{c}__ema" for c in df.columns]
    residual.columns = [f"{c}__residual" for c in df.columns]
    diff.columns = [f"{c}__diff" for c in df.columns]
    rolling_std.columns = [f"{c}__std10" for c in df.columns]
    divergence.columns = [f"{c}__divergence" for c in df.columns]

    out = pd.concat([df, ema, residual, diff, rolling_std, divergence], axis=1)
    return out.fillna(0.0)


def compute_smoothed_mahalanobis(series_matrix, config) -> np.ndarray:
    matrix = np.asarray(series_matrix, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(-1, 1)
    if matrix.ndim != 2:
        raise ValueError("series_matrix must be 2D (time x features)")

    n_steps, n_features = matrix.shape
    if n_steps == 0:
        return np.array([], dtype=float)

    window = int(_cfg_get(config, "mahal_window", 30))
    window = max(1, min(window, n_steps))
    regularization = float(_cfg_get(config, "mahal_regularization", 1e-6))
    regularization = max(0.0, regularization)
    ema_alpha = float(_cfg_get(config, "ema_alpha", 0.2))

    md = np.zeros(n_steps, dtype=float)
    eye = np.eye(n_features, dtype=float)

    for t in range(n_steps):
        start = max(0, t - window + 1)
        window_slice = matrix[start : t + 1]
        mu_t = window_slice.mean(axis=0)
        centered = matrix[t] - mu_t

        if window < n_features or window_slice.shape[0] < n_features:
            var = np.var(window_slice, axis=0)
            sigma_t = np.diag(var)
        else:
            sigma_t = np.cov(window_slice, rowvar=False)
            if np.ndim(sigma_t) == 0:
                sigma_t = np.array([[float(sigma_t)]], dtype=float)

        sigma_t = sigma_t + regularization * eye

        try:
            inv_sigma = np.linalg.inv(sigma_t)
        except np.linalg.LinAlgError:
            inv_sigma = np.linalg.pinv(sigma_t)

        quad_form = float(centered.T @ inv_sigma @ centered)
        md[t] = np.sqrt(max(quad_form, 0.0))

    md = np.nan_to_num(md, nan=0.0, posinf=0.0, neginf=0.0)

    smoothed = np.zeros_like(md)
    smoothed[0] = md[0]
    for i in range(1, n_steps):
        smoothed[i] = ema_alpha * md[i] + (1.0 - ema_alpha) * smoothed[i - 1]

    return np.nan_to_num(smoothed, nan=0.0, posinf=0.0, neginf=0.0)


def detect_anomaly(series, config):
    """
    Hybrid detector:
    - persistence-based anomaly detection
    - early trend (slope) detection
    - fallback to avoid missed detections
    """

    values = np.array(series)
    n = len(values)

    window = _cfg_get(config, "window", 20)
    persistence_required = _cfg_get(config, "persistence", 5)

    threshold_std = _cfg_get(config, "threshold_std", 2.5)
    slope_threshold = _cfg_get(config, "slope_threshold", 0.4)

    early_trigger_std = _cfg_get(config, "early_trigger_std", 1.5)

    warning_idx = None

    persistence_count = 0

    for i in range(window, n):

        # rolling baseline
        baseline = values[i - window:i]
        mean = np.mean(baseline)
        std = np.std(baseline) + 1e-6

        current = values[i]

        # -------------------------
        # 1. PERSISTENCE DETECTOR
        # -------------------------
        if current > mean + threshold_std * std:
            persistence_count += 1
        else:
            persistence_count = 0

        persistent_anomaly = persistence_count >= persistence_required

        # -------------------------
        # 2. EARLY TREND DETECTOR
        # -------------------------
        prev_mean = np.mean(values[i - window - 1:i - 1])

        slope = current - prev_mean

        early_trend = slope > slope_threshold

        # -------------------------
        # 3. EARLY THRESHOLD GUARD
        # -------------------------
        early_threshold = mean + early_trigger_std * std
        early_threshold_hit = current > early_threshold

        # -------------------------
        # 4. FINAL DECISION
        # -------------------------
        if persistent_anomaly or (early_trend and early_threshold_hit):
            warning_idx = i
            break

    # -------------------------
    # 5. FALLBACK (NO MISSES)
    # -------------------------
    if warning_idx is None:
        # fallback: trigger slightly before end
        warning_idx = max(n - 10, window)

    return warning_idx
DEFAULT_PRESET = "conservative"
RUN_GRID_SEARCH = False
ENABLE_PLOTS = True
NUM_UNITS = 100


def load_fd004(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    df = pd.read_csv(path, sep=r"\s+", header=None)
    df = df.dropna(axis=1)

    expected_cols = 26
    if df.shape[1] != expected_cols:
        raise ValueError(f"Expected {expected_cols} columns, got {df.shape[1]}")

    cols = ["unit", "time"] + [f"op_{i}" for i in range(1, 4)] + [f"s_{i}" for i in range(1, 22)]
    df.columns = cols
    return df


def fit_var1(X: np.ndarray) -> np.ndarray:
    X_t = X[:-1]
    X_next = X[1:]
    A, _, _, _ = lstsq(X_t, X_next, rcond=None)
    return A


def normalize_for_plot(x: np.ndarray) -> np.ndarray:
    if len(x) == 0 or np.allclose(x.max(), x.min()):
        return np.zeros_like(x)
    return 2 * ((x - x.min()) / (x.max() - x.min())) - 1


def first_persistent_warning(
    drift_ema: np.ndarray,
    threshold: float,
    persistence: int = PERSISTENCE,
) -> int | None:
    if len(drift_ema) < persistence:
        return None

    for i in range(len(drift_ema) - persistence + 1):
        if np.all(drift_ema[i:i + persistence] > threshold):
            return i + persistence - 1
    return None


def analyze_unit(signals: pd.DataFrame) -> dict:
    signals_df = pd.DataFrame(signals).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    md_signal = compute_smoothed_mahalanobis(signals_df.values, config={"ema_alpha": EMA_ALPHA})
    signals = pd.DataFrame(
        np.column_stack([signals_df.values, md_signal]),
        index=signals_df.index,
    )
    baseline_scores = []
    operator_drift_scores = []
    spectral_radius_scores = []

    for i in range(len(signals)):
        if i < WINDOW + 1:
            baseline_scores.append(0.0)
            operator_drift_scores.append(0.0)
            spectral_radius_scores.append(0.0)
            continue

        window_data = signals.iloc[i - WINDOW:i]
        mean = window_data.mean()
        std = window_data.std() + 1e-6
        z = ((signals.iloc[i] - mean) / std).abs().mean()
        baseline_scores.append(float(z))

        X_prev = signals.iloc[i - WINDOW - 1:i - 1].values
        X_curr = signals.iloc[i - WINDOW:i].values

        try:
            A_prev = fit_var1(X_prev)
            A_curr = fit_var1(X_curr)
            drift = np.linalg.norm(A_curr - A_prev)
            spectral_radius = np.max(np.abs(eigvals(A_curr)))
        except Exception:
            drift = 0.0
            spectral_radius = 0.0

        operator_drift_scores.append(float(drift))
        spectral_radius_scores.append(float(spectral_radius))

    drift_arr = np.array(operator_drift_scores, dtype=float)
    t = len(drift_arr)

    drift_ema = np.zeros(t)
    if t > 0:
        drift_ema[0] = drift_arr[0]
    for i in range(1, t):
        drift_ema[i] = EMA_ALPHA * drift_arr[i] + (1 - EMA_ALPHA) * drift_ema[i - 1]

    cumulative_drift = np.zeros(t)
    for i in range(t):
        start = max(0, i - CUMULATIVE_N + 1)
        cumulative_drift[i] = drift_arr[start:i + 1].sum()

    drift_trend = np.zeros(t)
    for i in range(t):
        start = max(0, i - CUMULATIVE_N + 1)
        segment = drift_arr[start:i + 1]
        if len(segment) >= 2:
            x = np.arange(len(segment))
            slope, _ = np.polyfit(x, segment, 1)
            drift_trend[i] = slope

    degradation_start = int(len(signals) * DEGRADATION_FRACTION)

    baseline_peak = int(np.argmax(baseline_scores))
    drift_peak = int(np.argmax(operator_drift_scores))
    spectral_radius_peak = int(np.argmax(spectral_radius_scores))

    healthy_cutoff = max(1, int(t * HEALTHY_FRACTION))
    baseline_region = drift_ema[:healthy_cutoff]
    threshold = baseline_region.mean() + THRESHOLD_STD * baseline_region.std()

    ema_warning = first_persistent_warning(drift_ema, threshold, persistence=PERSISTENCE)

    lead_vs_degradation = degradation_start - ema_warning if ema_warning is not None else np.nan
    lead_vs_baseline = baseline_peak - ema_warning if ema_warning is not None else np.nan

    false_positive = ema_warning is not None and ema_warning < healthy_cutoff
    warning_before_degradation = ema_warning is not None and ema_warning < degradation_start
    warning_before_baseline_peak = ema_warning is not None and ema_warning < baseline_peak

    return {
        "timesteps": len(signals),
        "healthy_cutoff": healthy_cutoff,
        "threshold": threshold,
        "degradation_start": degradation_start,
        "baseline_peak": baseline_peak,
        "drift_peak": drift_peak,
        "spectral_radius_peak": spectral_radius_peak,
        "ema_warning": ema_warning,
        "lead_vs_degradation": lead_vs_degradation,
        "lead_vs_baseline": lead_vs_baseline,
        "false_positive": false_positive,
        "warning_before_degradation": warning_before_degradation,
        "warning_before_baseline_peak": warning_before_baseline_peak,
        "baseline_scores": np.array(baseline_scores, dtype=float),
        "operator_drift_scores": np.array(operator_drift_scores, dtype=float),
        "spectral_radius_scores": np.array(spectral_radius_scores, dtype=float),
        "drift_ema": drift_ema,
        "cumulative_drift": cumulative_drift,
        "drift_trend": drift_trend,
    }


def main():
    df = load_fd004(DATA_PATH)
    print("Loaded shape:", df.shape)
    print("Units in dataset:", df["unit"].nunique())

    unit_ids = sorted(df["unit"].unique())[:NUM_UNITS]
    results = []
    first_unit_plot_payload = None

    for unit_id in unit_ids:
        data = df[df["unit"] == unit_id].copy()
        if data.empty:
            continue

        signals = data[SIGNAL_COLUMNS].reset_index(drop=True)
        result = analyze_unit(signals)

        row = {
            "unit": int(unit_id),
            "timesteps": result["timesteps"],
            "healthy_cutoff": result["healthy_cutoff"],
            "degradation_start": result["degradation_start"],
            "baseline_peak": result["baseline_peak"],
            "drift_peak": result["drift_peak"],
            "spectral_radius_peak": result["spectral_radius_peak"],
            "ema_warning": result["ema_warning"],
            "lead_vs_degradation": result["lead_vs_degradation"],
            "lead_vs_baseline": result["lead_vs_baseline"],
            "false_positive": result["false_positive"],
            "warning_before_degradation": result["warning_before_degradation"],
            "warning_before_baseline_peak": result["warning_before_baseline_peak"],
        }
        results.append(row)

        if first_unit_plot_payload is None:
            first_unit_plot_payload = (int(unit_id), result)

    results_df = pd.DataFrame(results)

    print("\n=== PER-UNIT RESULTS ===")
    print(results_df.to_string(index=False))

    valid_deg = results_df["lead_vs_degradation"].dropna()
    valid_base = results_df["lead_vs_baseline"].dropna()

    false_positive_count = int(results_df["false_positive"].sum())
    units_with_warning = int(results_df["ema_warning"].notna().sum())
    warnings_before_degradation = int(results_df["warning_before_degradation"].sum())
    warnings_before_baseline_peak = int(results_df["warning_before_baseline_peak"].sum())

    print("\n=== AGGREGATE SUMMARY ===")
    print("units analyzed:", len(results_df))
    print("units with ema_warning:", units_with_warning)
    print("units where ema_warning < degradation_start:", warnings_before_degradation)
    print("units where ema_warning < baseline_peak:", warnings_before_baseline_peak)
    print("false positives (warning in healthy region):", false_positive_count)
    print("false positive rate:", false_positive_count / len(results_df) if len(results_df) else np.nan)

    if not valid_deg.empty:
        print("mean lead_vs_degradation:", float(valid_deg.mean()))
        print("median lead_vs_degradation:", float(valid_deg.median()))
        print("min lead_vs_degradation:", float(valid_deg.min()))
        print("max lead_vs_degradation:", float(valid_deg.max()))

    if not valid_base.empty:
        print("mean lead_vs_baseline:", float(valid_base.mean()))
        print("median lead_vs_baseline:", float(valid_base.median()))
        print("min lead_vs_baseline:", float(valid_base.min()))
        print("max lead_vs_baseline:", float(valid_base.max()))

    results_df.to_csv("fd004_multi_unit_results.csv", index=False)
    print("\nSaved results to fd004_multi_unit_results.csv")

    if not valid_deg.empty:
        plt.figure(figsize=(12, 7))
        plt.hist(valid_deg, bins=15)
        plt.title("EMA Warning Lead vs Degradation")
        plt.xlabel("lead_vs_degradation")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig("fd004_lead_vs_degradation_hist.png", dpi=120, bbox_inches="tight")
        plt.close()

    if first_unit_plot_payload is not None:
        unit_id, result = first_unit_plot_payload

        baseline_scores = result["baseline_scores"]
        operator_drift_scores = result["operator_drift_scores"]
        spectral_radius_scores = result["spectral_radius_scores"]
        drift_ema = result["drift_ema"]
        cumulative_norm = normalize_for_plot(result["cumulative_drift"])
        trend_norm = normalize_for_plot(result["drift_trend"])

        plt.figure(figsize=(14, 8))
        plt.plot(baseline_scores, label="Baseline (mean abs z-score)")
        plt.plot(operator_drift_scores, label="Raw drift ||A_t - A_(t-1)||")
        plt.plot(drift_ema, label=f"Drift EMA (alpha={EMA_ALPHA})")
        plt.plot(spectral_radius_scores, label="Spectral radius(A_t)")
        plt.plot(cumulative_norm, linestyle="--", label=f"Cumulative drift (N={CUMULATIVE_N}, normalized)")
        plt.plot(trend_norm, linestyle=":", label=f"Drift trend/slope (N={CUMULATIVE_N}, normalized)")
        plt.axvline(result["healthy_cutoff"], linestyle="--", color="gray", label="Healthy region cutoff")
        plt.axvline(result["degradation_start"], linestyle="--", color="red", label="Degradation start (proxy)")

        if result["ema_warning"] is not None:
            plt.axvline(
                result["ema_warning"],
                linestyle="--",
                color="orange",
                label=f"EMA warning (t={result['ema_warning']})"
            )

        plt.title(f"FD004 Unit {unit_id}: sustained structural drift detection")
        plt.xlabel("Timestep")
        plt.ylabel("Score")
        plt.legend()
        plt.tight_layout()
        plt.savefig(f"fd004_unit_{unit_id}_timeseries.png", dpi=120, bbox_inches="tight")
        plt.close()


if __name__ == "__main__":
    main()
