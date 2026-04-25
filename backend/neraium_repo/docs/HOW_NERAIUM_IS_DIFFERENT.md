# How Neraium Is Different From Predictive Maintenance and AI Monitoring

Most monitoring and predictive maintenance systems analyze **individual sensors or components**. They look for threshold violations, abnormal readings, or patterns that match previous failures.

**Neraium takes a fundamentally different approach.**

Instead of asking whether a single component is failing, Neraium analyzes the **stability of the system itself**.

---

## Traditional predictive maintenance

Predictive maintenance systems typically work by:

- Monitoring individual sensor values  
- Detecting anomalies in a specific signal  
- Predicting component failure based on historical data  

For example, a traditional system might detect that:

- Vibration is rising on a bearing  
- Temperature exceeds a limit  
- Pressure drops below a threshold  

These systems usually detect problems **after degradation has already begun**.

They also depend heavily on **historical failure data** and training datasets.

---

## Typical AI monitoring systems

Many modern monitoring platforms use machine learning or AI models to detect anomalies.

These systems:

- Train models on historical telemetry data  
- Learn patterns of “normal” behavior  
- Flag deviations from those patterns  

While this approach can detect unusual signals, it still focuses primarily on **individual sensor behavior** rather than the **structure of the entire system**.

AI models also require **large datasets** and often behave as **black boxes**, making it difficult for operators to understand **why** alerts occur.

---

## The Neraium approach

Neraium focuses on **systemic stability**, not just sensor anomalies.

The platform continuously analyzes the **relationships between signals** across machines and infrastructure to determine whether the system is **moving toward instability**.

Instead of predicting *when* a component will fail, Neraium identifies when the system is **approaching a critical transition**.

This allows the platform to detect **emerging risk** much earlier than many traditional predictive systems.

---

## What Neraium detects

Neraium identifies patterns that appear when complex systems begin to **lose stability**, including:

- Changes in how sensors **interact** with each other  
- **Structural drift** across system signals  
- Rising instability across **fleets** of machines  
- **Regime shifts** in operational behavior  
- **Precursor signals** that appear before failure  

These patterns often emerge **well before** component-level indicators become obvious.

---

## Why this matters

Because Neraium analyzes **systemic behavior**, it can support **earlier detection** and **richer operational insight** in many environments.

Compared to traditional approaches, Neraium is designed to offer:

| Benefit | What it means |
|--------|----------------|
| **Earlier detection** | Problems can surface before component degradation is obvious. |
| **System-level visibility** | Operators see how instability develops **across** a system, not only inside one machine. |
| **Less dependence on past failures** | Structural signals of instability complement, not replace, historical failure data. |
| **Clearer operational insights** | Alerts tie to **identifiable system behaviors** rather than opaque model scores alone. |

---

## In simple terms

**Traditional systems ask:**  
*“Is this component failing?”*

**AI monitoring systems often ask:**  
*“Does this sensor look unusual?”*

**Neraium asks:**  
*“Is the system itself becoming unstable?”*

That shift helps operators spot **emerging risk** earlier and make better decisions **before** failures occur.

---

## Relationship to this repository

`neraium-core` implements **Systemic Infrastructure Intelligence (SII)** as a **read-only** instrumentation layer: multivariate telemetry in, structural stability evidence out. It is **not** a generic anomaly detector or a classical predictive-maintenance classifier trained on failure labels alone.

For deployment constraints, API usage, and mathematical implementation details, see the [project README](../README.md).
