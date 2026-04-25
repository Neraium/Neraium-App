# Mathematical upgrade notes (March 2026)

## Dependence estimation backends

The geometry layer now supports interchangeable dependence estimators:

- `pearson` (default): fastest and most direct linear coupling estimate.
- `spearman`: rank-based, more robust to monotonic nonlinear effects and outliers.
- `partial`: shrinkage precision-matrix estimate; helps isolate conditional relationships and suppress indirect coupling.

Optional lag differencing (`SII_DEPENDENCE_LAG`) supports simple lag-aware dependence.

Tradeoffs:
- Pearson: lowest compute cost, highest interpretability, lower robustness to outliers.
- Spearman: moderate compute cost, stronger robustness, slightly less direct magnitude interpretation.
- Partial: highest compute cost, best structural disambiguation, most sensitive to sample size.

## Regime awareness

Regime memory remains prototype-based for interpretability, and is now augmented with
Bayesian posterior smoothing over nearest-regime likelihoods.

New outputs include:
- `regime_memory.confidence`
- `regime_memory.uncertainty`

This makes mode shifts vs novelty more explicit without claiming formal latent-state identification.

## Transition forecasting

Forward risk now includes a transparent probabilistic transition layer:

- Smoothed Markov transition probabilities across latent `stable/drift/unstable` bins.
- Hazard-style escalation score (`evidence.hazard`).
- Explicit uncertainty (`evidence.uncertainty`, transition entropy).

This replaces pure deterministic trend extrapolation while retaining explainability.

## Dynamic graph metrics

Temporal graph observables now include:
- edge persistence
- edge birth/death rates
- centrality shift
- dynamic fragility score

These metrics are surfaced under `experimental_analytics.graph_metrics` and can be tied to
structural drift and subsystem instability in operator explanations.

## Hypothesis scoring

Causal interpretation remains observational-only.

Hypothesis ranking now uses explicit evidence decomposition across localization,
persistence, subsystem coherence, robustness, and multi-signal agreement.
