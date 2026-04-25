import pandas as pd

files = {
    "best_fd004": "FD004_scored.csv",
    "ims_tuned": "FD004_ims_policy_tuned_scored.csv",
    "ims_original": "FD004_ims_policy_scored.csv",
}

rows = []

for name, path in files.items():
    try:
        df = pd.read_csv(path)
    except:
        continue

    total = len(df)
    has_alert = df["has_alert"].sum()

    coverage = has_alert / total if total else 0

    lead = df.loc[df["has_alert"], "alert_lead"]

    row = {
        "policy": name,
        "coverage": round(coverage, 4),
        "mean_lead": round(lead.mean(), 2) if len(lead) else None,
        "median_lead": round(lead.median(), 2) if len(lead) else None,
        "misses": int((~df["has_alert"]).sum()),
        "good": int((df["alert_quality"] == "good").sum()),
        "very_early": int((df["alert_quality"] == "very_early").sum()),
        "usable": int((df["alert_quality"] == "usable").sum()),
        "late": int((df["alert_quality"] == "late").sum()),
    }

    rows.append(row)

out = pd.DataFrame(rows).sort_values("coverage", ascending=False)

print("\nFD004 POLICY COMPARISON")
print("=" * 60)
print(out.to_string(index=False))

out.to_csv("FD004_policy_comparison.csv", index=False)

print("\nSaved: FD004_policy_comparison.csv")
