import pandas as pd
import matplotlib.pyplot as plt

# load results
df = pd.read_csv("IMS_quick_results.csv")

print("rows:", len(df))
print(df.head())

# -----------------------------
# Convert states to numeric for plotting
# -----------------------------
state_map = {
    "STABLE": 0,
    "WATCH": 1,
    "ALERT": 2
}

df["state_num"] = df["state"].map(state_map)

# -----------------------------
# Plot 1: Drift score over time
# -----------------------------
plt.figure(figsize=(12, 6))
plt.plot(df["file_index"], df["structural_drift_score"])
plt.xlabel("Time (file index)")
plt.ylabel("Structural Drift Score")
plt.title("IMS Drift Over Time")
plt.tight_layout()
plt.savefig("ims_drift_over_time.png", dpi=200)
plt.show()

# -----------------------------
# Plot 2: State transitions
# -----------------------------
plt.figure(figsize=(12, 4))
plt.plot(df["file_index"], df["state_num"])
plt.yticks([0, 1, 2], ["STABLE", "WATCH", "ALERT"])
plt.xlabel("Time (file index)")
plt.ylabel("State")
plt.title("IMS State Transitions")
plt.tight_layout()
plt.savefig("ims_state_transitions.png", dpi=200)
plt.show()

# -----------------------------
# Plot 3: Drift + Alerts overlay
# -----------------------------
plt.figure(figsize=(12, 6))
plt.plot(df["file_index"], df["structural_drift_score"], label="Drift Score")

alerts = df[df["state"] == "ALERT"]
plt.scatter(alerts["file_index"], alerts["structural_drift_score"], label="ALERT")

plt.xlabel("Time")
plt.ylabel("Drift Score")
plt.title("Drift with Alert Points")
plt.legend()
plt.tight_layout()
plt.savefig("ims_alert_overlay.png", dpi=200)
plt.show()

print("\nSaved plots:")
print(" - ims_drift_over_time.png")
print(" - ims_state_transitions.png")
print(" - ims_alert_overlay.png")
