# Structural System Intelligence Upgrade

This upgrade introduces a production-minded **structural system intelligence** layer that extends the existing SII drift/risk engine with six integrated capabilities:

1. **Latent structural state space** (`neraium_core/system_intelligence/structural_state/latent_state.py`)
   - Streaming interpretable latent state via normalized structural feature vectors and SVD basis projection.
   - Exposes embedding, summary loadings, trajectory, velocity, acceleration.

2. **Transition dynamics** (`neraium_core/system_intelligence/transition_model/transition_dynamics.py`)
   - Latent trajectory transition model with regime assignment (`stable/transitional/critical`) and path typing (`stable/drifting/reversible/escalating`).
   - Outputs escalation probability, reversibility score, distance-to-critical region, uncertainty.

3. **Counterfactual intervention engine** (`neraium_core/system_intelligence/counterfactuals/intervention_engine.py`)
   - Approximate intervention scenarios under explicit assumptions (no formal causality claims).
   - Supports removing top driver contribution, restoring relationship clusters, suppressing subsystem instability.

4. **Cross-system archetype learning** (`neraium_core/system_intelligence/archetypes/archetype_memory.py`)
   - Online latent-space archetype centroids with similarity ranking and archetype-level escalation frequency.
   - Supports matching current trajectory to known archetypes/pathways.

5. **Mechanism discovery** (`neraium_core/system_intelligence/mechanisms/discovery.py`)
   - Interpretable candidate mechanisms from recurring triad weakening motifs and subsystem decoupling signatures.
   - Scores candidates by recurrence, motif strength, and predictive value.

6. **Product-grade integration** (`neraium_core/sii/engine.py`)
   - Adds `structural_system_intelligence` payload into every non-error SII result (warmup status when history is insufficient).
   - Preserves compatibility with existing `risk_assessment`, `operator_guidance`, `causal_analysis`, and decision outputs.

## Schema Overview

`result.structural_system_intelligence` contains:
- `latent_structural_state`
- `transition_dynamics`
- `counterfactuals`
- `archetype_intelligence`
- `mechanism_discovery`
- `compatibility` (adapter summary for phase/trend/risk-level style consumption)

## Scientific Boundaries

- Counterfactuals are **structural simulations under assumptions**, not identified causal effects.
- Mechanism outputs are **candidate mechanisms**, ranked by evidence criteria, not proof of physical causation.
- Transition probabilities are calibrated from latent dynamics + empirical counts and should be validated per deployment.

## Validation

Integration validation test:
- `tests/test_structural_system_intelligence_upgrade.py`

It verifies:
- trajectory-aware latent outputs are produced,
- escalation probability increases under induced regime break,
- counterfactual risk changes are directionally sensible,
- archetype and mechanism layers produce non-empty structured outputs,
- legacy operator-facing outputs remain present.
