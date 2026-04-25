# Reliability Validation Artifacts

Synthetic calibration progression for repeated matched contexts.

| step | traj_raw | traj_cal_short | rec_raw | rec_cal | rec_bucket_support |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.740 | 0.509 | 0.630 | 0.425 | 0 |
| 2 | 0.740 | 0.509 | 0.630 | 0.425 | 0 |
| 3 | 0.740 | 0.509 | 0.630 | 0.425 | 0 |
| 4 | 0.740 | 0.535 | 0.630 | 0.460 | 3 |
| 5 | 0.740 | 0.580 | 0.630 | 0.504 | 4 |
| 6 | 0.740 | 0.580 | 0.630 | 0.507 | 5 |
| 7 | 0.740 | 0.580 | 0.630 | 0.511 | 6 |
| 8 | 0.740 | 0.580 | 0.630 | 0.514 | 7 |
| 9 | 0.740 | 0.625 | 0.630 | 0.559 | 8 |

## Notes
- Calibrated values are conservative early (warmup) and become less discounted as support accumulates.
- Bucket support and fallback behavior are inspectable through reliability traces.