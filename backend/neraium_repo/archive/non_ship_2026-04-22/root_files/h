warning: in the working copy of 'neraium_core/engine_stages/scoring_preparation.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'neraium_core/features/window_feature_extractor.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'neraium_core/staged_pipeline.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'run_demo.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'ui/unified_shell_data.py', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/frontend/components/TeslaAutopilotInterface.tsx b/frontend/components/TeslaAutopilotInterface.tsx[m
[1mindex 433c0f73..6c3a1617 100644[m
[1m--- a/frontend/components/TeslaAutopilotInterface.tsx[m
[1m+++ b/frontend/components/TeslaAutopilotInterface.tsx[m
[36m@@ -1,4 +1,4 @@[m
[31m-'use client'[m
[32m+[m[32m﻿'use client'[m
 [m
 import React, { useState, useEffect } from 'react'[m
 import { motion } from 'framer-motion'[m
[36m@@ -321,7 +321,7 @@[m [mexport function TeslaAutopilotInterface({[m
                 }}[m
                 onMouseEnter={e => { e.currentTarget.style.color = '#94a3b8'; e.currentTarget.style.borderColor = 'rgba(100,116,139,0.5)' }}[m
                 onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(100,116,139,0.25)' }}[m
[31m-              >‹</button>[m
[32m+[m[32m              >â€¹</button>[m
               <button[m
                 onClick={() => onStepScenario(1)}[m
                 style={{[m
[36m@@ -340,7 +340,7 @@[m [mexport function TeslaAutopilotInterface({[m
                 }}[m
                 onMouseEnter={e => { e.currentTarget.style.color = '#94a3b8'; e.currentTarget.style.borderColor = 'rgba(100,116,139,0.5)' }}[m
                 onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(100,116,139,0.25)' }}[m
[31m-              >›</button>[m
[32m+[m[32m              >â€º</button>[m
             </div>[m
           )}[m
 [m
[36m@@ -362,7 +362,7 @@[m [mexport function TeslaAutopilotInterface({[m
             onMouseEnter={e => { e.currentTarget.style.background = `${stateColor}28` }}[m
             onMouseLeave={e => { e.currentTarget.style.background = isPlaying ? `${stateColor}1a` : 'rgba(126,159,46,0.12)' }}[m
           >[m
[31m-            {isPlaying ? '❙❙ Pause' : '▶ Play'}[m
[32m+[m[32m            {isPlaying ? 'â™â™ Pause' : 'â–¶ Play'}[m
           </button>[m
         </div>[m
       </motion.div>[m
[36m@@ -483,19 +483,21 @@[m [mexport function TeslaAutopilotInterface({[m
                 transition={{ duration: 0.4 }}[m
                 style={{[m
                   position: 'absolute',[m
[31m-                  bottom: 60,[m
[31m-                  left: '50%',[m
[31m-                  transform: 'translateX(-50%)',[m
[32m+[m[32m                  bottom: 18,[m
[32m+[m[32m                  right: 18,[m
[32m+[m[32m                  left: 'auto',[m
[32m+[m[32m                  transform: 'none',[m
                   background: 'rgba(5,6,7,0.9)',[m
                   backdropFilter: 'blur(12px)',[m
                   border: `1px solid ${stateColor}33`,[m
                   borderTop: `2px solid ${stateColor}66`,[m
                   borderRadius: '8px',[m
[31m-                  padding: '14px 22px',[m
[31m-                  maxWidth: '360px',[m
[31m-                  minWidth: '260px',[m
[32m+[m[32m                  padding: '12px 16px',[m
[32m+[m[32m                  maxWidth: 'min(320px, 38vw)',[m
[32m+[m[32m                  minWidth: '220px',[m
                   textAlign: 'center',[m
                   zIndex: 30,[m
[32m+[m[32m                  pointerEvents: 'none',[m
                 }}[m
               >[m
                 <div style={{ fontSize: '10px', color: '#334155', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '5px', fontWeight: 700 }}>[m
[36m@@ -530,10 +532,10 @@[m [mexport function TeslaAutopilotInterface({[m
               }}[m
             >[m
               {[[m
[31m-                { label: 'Airflow', color: '#7e9f2e', dir: '↑' },[m
[31m-                { label: 'Climate', color: '#d8a35d', dir: '→' },[m
[31m-                { label: 'Irrigation', color: '#7e9f2e', dir: '↓' },[m
[31m-                { label: 'Plant Stress', color: '#c94c4c', dir: '↑' },[m
[32m+[m[32m                { label: 'Airflow', color: '#7e9f2e', dir: 'â†‘' },[m
[32m+[m[32m                { label: 'Climate', color: '#d8a35d', dir: 'â†’' },[m
[32m+[m[32m                { label: 'Irrigation', color: '#7e9f2e', dir: 'â†“' },[m
[32m+[m[32m                { label: 'Plant Stress', color: '#c94c4c', dir: 'â†‘' },[m
               ].map(s => ([m
                 <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>[m
                   <span>{s.label}</span>[m
[36m@@ -663,3 +665,5 @@[m [mexport function TeslaAutopilotInterface({[m
     </div>[m
   )[m
 }[m
[41m+[m
[41m+[m
[1mdiff --git a/neraium_core/engine_stages/scoring_preparation.py b/neraium_core/engine_stages/scoring_preparation.py[m
[1mindex faf59415..27755d91 100644[m
[1m--- a/neraium_core/engine_stages/scoring_preparation.py[m
[1m+++ b/neraium_core/engine_stages/scoring_preparation.py[m
[36m@@ -1,4 +1,4 @@[m
[31m-from __future__ import annotations[m
[32m+[m[32m﻿from __future__ import annotations[m
 [m
 from dataclasses import dataclass[m
 from typing import Any, Protocol[m
[36m@@ -44,8 +44,7 @@[m [mdef prepare_scoring_inputs([m
     correlation_ready = stage_input.valid_signal_count >= 2[m
     covariance_ready = correlation_ready[m
     minimum_sample_ready = correlation_ready[m
[31m-[m
[31m-    if not correlation_ready:[m
[32m+[m[32m    if not correlation_ready or not minimum_sample_ready:[m
         return ScoringPreparationResult([m
             should_proceed_scoring=False,[m
             correlation_ready=correlation_ready,[m
[36m@@ -60,13 +59,27 @@[m [mdef prepare_scoring_inputs([m
             baseline_corr_used=None,[m
             baseline_mode=None,[m
         )[m
[31m-[m
     z_base_valid = stage_input.z_baseline[:, stage_input.valid_mask][m
     z_recent_valid = stage_input.z_recent[:, stage_input.valid_mask][m
[31m-    stage_features = FeatureExtractionStage.extract(z_base_valid, z_recent_valid)[m
[31m-[m
[31m-    corr_baseline = correlation_matrix(z_base_valid)[m
[31m-    corr_recent = correlation_matrix(z_recent_valid)[m
[32m+[m[32m    try:[m
[32m+[m[32m        stage_features = FeatureExtractionStage.extract(z_base_valid, z_recent_valid)[m
[32m+[m[32m        corr_baseline = correlation_matrix(z_base_valid)[m
[32m+[m[32m        corr_recent = correlation_matrix(z_recent_valid)[m
[32m+[m[32m    except Exception:[m
[32m+[m[32m        return ScoringPreparationResult([m
[32m+[m[32m            should_proceed_scoring=False,[m
[32m+[m[32m            correlation_ready=correlation_ready,[m
[32m+[m[32m            covariance_ready=covariance_ready,[m
[32m+[m[32m            minimum_sample_ready=minimum_sample_ready,[m
[32m+[m[32m            shape_compatible=False,[m
[32m+[m[32m            z_baseline_valid=None,[m
[32m+[m[32m            z_recent_valid=None,[m
[32m+[m[32m            stage_features=None,[m
[32m+[m[32m            corr_baseline=None,[m
[32m+[m[32m            corr_recent=None,[m
[32m+[m[32m            baseline_corr_used=None,[m
[32m+[m[32m            baseline_mode=None,[m
[32m+[m[32m        )[m
 [m
     baseline_corr_used = corr_baseline[m
     baseline_mode = "fixed"[m
[36m@@ -91,3 +104,4 @@[m [mdef prepare_scoring_inputs([m
         baseline_corr_used=baseline_corr_used,[m
         baseline_mode=baseline_mode,[m
     )[m
[41m+[m
[1mdiff --git a/neraium_core/features/window_feature_extractor.py b/neraium_core/features/window_feature_extractor.py[m
[1mindex 6a7a3f3e..3c3a946c 100644[m
[1m--- a/neraium_core/features/window_feature_extractor.py[m
[1m+++ b/neraium_core/features/window_feature_extractor.py[m
[36m@@ -1,4 +1,4 @@[m
[31m-from __future__ import annotations[m
[32m+[m[32m﻿from __future__ import annotations[m
 [m
 from dataclasses import dataclass[m
 from typing import Any[m
[36m@@ -101,7 +101,8 @@[m [mdef _channel_feature_vector(x: np.ndarray) -> dict[str, float]:[m
 [m
 def _cross_channel_features(matrix: np.ndarray) -> dict[str, float]:[m
     n_channels = int(matrix.shape[1])[m
[31m-    if n_channels < 2:[m
[32m+[m[32m    n_obs = int(matrix.shape[0])[m
[32m+[m[32m    if n_channels < 2 or n_obs < 2:[m
         return {[m
             "channel_corr_mean": 1.0,[m
             "channel_corr_std": 0.0,[m
[36m@@ -200,3 +201,4 @@[m [mdef summarize_feature_delta([m
             "feature_consistency_breakdown": consistency_breakdown,[m
         },[m
     }[m
[41m+[m
[1mdiff --git a/neraium_core/staged_pipeline.py b/neraium_core/staged_pipeline.py[m
[1mindex 8152da14..6a26215e 100644[m
[1m--- a/neraium_core/staged_pipeline.py[m
[1m+++ b/neraium_core/staged_pipeline.py[m
[36m@@ -1,4 +1,4 @@[m
[31m-from __future__ import annotations[m
[32m+[m[32m﻿from __future__ import annotations[m
 [m
 from collections import deque[m
 from dataclasses import dataclass, field[m
[36m@@ -21,11 +21,30 @@[m [mdef bounded_z(raw: float, mean: float, std: float, cap: float = 4.0) -> float:[m
 [m
 [m
 def corr_from_matrix(m: np.ndarray) -> np.ndarray:[m
[32m+[m[32m    m = np.asarray(m, dtype=float)[m
[32m+[m[32m    if m.ndim != 2:[m
[32m+[m[32m        raise ValueError("Expected 2D matrix")[m
[32m+[m[32m    n_obs = int(m.shape[0])[m
[32m+[m[32m    n_features = int(m.shape[1])[m
[32m+[m[32m    if n_features == 0:[m
[32m+[m[32m        return np.zeros((0, 0), dtype=float)[m
[32m+[m[32m    # Correlation needs >= 2 observations; return identity to avoid undefined[m
[32m+[m[32m    # geometry in warmup/degenerate windows.[m
[32m+[m[32m    if n_obs < 2:[m
[32m+[m[32m        return np.eye(n_features, dtype=float)[m
[32m+[m
     with np.errstate(invalid="ignore", divide="ignore"):[m
         corr = np.corrcoef(m.T)[m
     corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)[m
     np.fill_diagonal(corr, 1.0)[m
[31m-    return corr[m
[32m+[m
[32m+[m[32m    # Light shrinkage toward identity when observation/feature ratio is small.[m
[32m+[m[32m    ratio = float(n_features) / float(max(1, n_obs))[m
[32m+[m[32m    shrink = clamp(0.12 * ratio, 0.0, 0.35)[m
[32m+[m[32m    if shrink > 0.0:[m
[32m+[m[32m        corr = (1.0 - shrink) * corr + shrink * np.eye(n_features, dtype=float)[m
[32m+[m[32m        np.fill_diagonal(corr, 1.0)[m
[32m+[m[32m    return np.asarray(corr, dtype=float)[m
 [m
 [m
 def flatten_upper_tri(m: np.ndarray) -> np.ndarray:[m
[36m@@ -234,12 +253,24 @@[m [mclass DataQualityStage:[m
 class FeatureExtractionStage:[m
     @staticmethod[m
     def extract(baseline: np.ndarray, recent: np.ndarray) -> dict[str, Any]:[m
[31m-        base_mean = np.mean(baseline, axis=0)[m
[31m-        rec_mean = np.mean(recent, axis=0)[m
[31m-        base_std = np.std(baseline, axis=0)[m
[31m-        rec_std = np.std(recent, axis=0)[m
[31m-        corr_base = corr_from_matrix(baseline)[m
[31m-        corr_recent = corr_from_matrix(recent)[m
[32m+[m[32m        baseline = np.asarray(baseline, dtype=float)[m
[32m+[m[32m        recent = np.asarray(recent, dtype=float)[m
[32m+[m[32m        if baseline.ndim != 2 or recent.ndim != 2:[m
[32m+[m[32m            raise ValueError("Expected 2D baseline/recent windows")[m
[32m+[m
[32m+[m[32m        # Keep NaNs from propagating into feature vectors during warmup.[m
[32m+[m[32m        with np.errstate(invalid="ignore", divide="ignore"):[m
[32m+[m[32m            base_mean = np.nanmean(baseline, axis=0) if baseline.size else np.array([], dtype=float)[m
[32m+[m[32m            rec_mean = np.nanmean(recent, axis=0) if recent.size else np.array([], dtype=float)[m
[32m+[m[32m            base_std = np.nanstd(baseline, axis=0) if baseline.size else np.array([], dtype=float)[m
[32m+[m[32m            rec_std = np.nanstd(recent, axis=0) if recent.size else np.array([], dtype=float)[m
[32m+[m[32m        base_mean = np.nan_to_num(base_mean, nan=0.0, posinf=0.0, neginf=0.0)[m
[32m+[m[32m        rec_mean = np.nan_to_num(rec_mean, nan=0.0, posinf=0.0, neginf=0.0)[m
[32m+[m[32m        base_std = np.nan_to_num(base_std, nan=0.0, posinf=0.0, neginf=0.0)[m
[32m+[m[32m        rec_std = np.nan_to_num(rec_std, nan=0.0, posinf=0.0, neginf=0.0)[m
[32m+[m
[32m+[m[32m        corr_base = corr_from_matrix(np.nan_to_num(baseline, nan=0.0, posinf=0.0, neginf=0.0))[m
[32m+[m[32m        corr_recent = corr_from_matrix(np.nan_to_num(recent, nan=0.0, posinf=0.0, neginf=0.0))[m
         rel_vec_base = flatten_upper_tri(corr_base)[m
         rel_vec_recent = flatten_upper_tri(corr_recent)[m
         signature = np.concatenate([rec_mean, rec_std, rel_vec_recent])[m
[36m@@ -399,7 +430,7 @@[m [mclass DecisionStage:[m
 [m
     @staticmethod[m
     def adjusted_instability(instability: float, confidence: float, localization: float) -> float:[m
[31m-        """Same inner product as state_from_score (instability × loc_gate × conf_gate), exposed for calibration."""[m
[32m+[m[32m        """Same inner product as state_from_score (instability Ã— loc_gate Ã— conf_gate), exposed for calibration."""[m
         loc_gate = 0.40 + 0.60 * float(localization)[m
         conf_gate = 0.55 + 0.45 * float(confidence)[m
         return float(max(0.0, float(instability) * loc_gate * conf_gate))[m
[36m@@ -424,7 +455,7 @@[m [mdef adaptive_gal2_fusion_coherence([m
     Adaptive GAL-2 calibration for SII+GAL-2 *fusion* paths.[m
 [m
     Under disturbed clocks, raw temporal_coherence is often low while GAL-2 still reports[m
[31m-    meaningful timing distortion. Multiplicative fusion terms (instability × coherence) then[m
[32m+[m[32m    meaningful timing distortion. Multiplicative fusion terms (instability Ã— coherence) then[m
     collapse and the Combined lane is underpowered. This blends in a bounded, distortion-driven[m
     coupling term: higher distortion raises effective coherence only where coherence was weak,[m
     preserving strong-coherent regimes unchanged.[m
[36m@@ -493,3 +524,5 @@[m [mclass AttributionStage:[m
         msg = f"{state}: dominated by {', '.join(top)}." if top else f"{state}: no dominant structural drivers."[m
         return msg, contrib[m
 [m
[41m+[m
[41m+[m
[1mdiff --git a/run_demo.py b/run_demo.py[m
[1mindex caa01ec2..947db5c6 100644[m
[1m--- a/run_demo.py[m
[1m+++ b/run_demo.py[m
[36m@@ -1,8 +1,15 @@[m
[31m-#!/usr/bin/env python3[m
[32m+[m[32m﻿#!/usr/bin/env python3[m
 """Run Neraium demo using FastAPI backend + Next.js frontend.[m
 [m
 Primary demo command:[m
     python run_demo.py[m
[32m+[m
[32m+[m[32mTo run the demo UI on a custom port (e.g. http://localhost:3004):[m
[32m+[m[32m    python run_demo.py --frontend-port 3004[m
[32m+[m
[32m+[m[32mThis launcher is resilient to ports already in use:[m
[32m+[m[32m- Backend: if the configured port is already serving Neraium, it reuses it; otherwise it picks the next free port.[m
[32m+[m[32m- Frontend: if the configured port is already serving a frontend, it does not try to start a second copy.[m
 """[m
 [m
 from __future__ import annotations[m
[36m@@ -10,11 +17,13 @@[m [mfrom __future__ import annotations[m
 import argparse[m
 import os[m
 import shutil[m
[31m-import signal[m
[32m+[m[32mimport socket[m
 import subprocess[m
 import sys[m
 import time[m
 from pathlib import Path[m
[32m+[m[32mfrom urllib import error as urlerror[m
[32m+[m[32mfrom urllib import request as urlrequest[m
 [m
 REPO_ROOT = Path(__file__).resolve().parent[m
 FRONTEND_DIR = REPO_ROOT / "frontend"[m
[36m@@ -46,6 +55,56 @@[m [mdef _ensure_frontend_dependencies() -> None:[m
         _run([npm, "install"], cwd=FRONTEND_DIR)[m
 [m
 [m
[32m+[m[32mdef _is_port_listening(port: int, host: str = "127.0.0.1") -> bool:[m
[32m+[m[32m    try:[m
[32m+[m[32m        with socket.create_connection((host, int(port)), timeout=0.35):[m
[32m+[m[32m            return True[m
[32m+[m[32m    except OSError:[m
[32m+[m[32m        return False[m
[32m+[m
[32m+[m
[32m+[m[32mdef _probe_neraium_backend(port: int) -> bool:[m
[32m+[m[32m    """Return True if localhost:{port} looks like Neraium FastAPI."""[m
[32m+[m[32m    p = int(port)[m
[32m+[m[32m    # Fast path: OpenAPI is cheap and includes the app title.[m
[32m+[m[32m    openapi_url = f"http://127.0.0.1:{p}/openapi.json"[m
[32m+[m[32m    try:[m
[32m+[m[32m        with urlrequest.urlopen(openapi_url, timeout=0.8) as resp:[m
[32m+[m[32m            if int(getattr(resp, "status", 0) or 0) != 200:[m
[32m+[m[32m                return False[m
[32m+[m[32m            body = resp.read(8192) or b""[m
[32m+[m[32m        text = body.decode("utf-8", errors="ignore")[m
[32m+[m[32m        if "Neraium SII API" in text:[m
[32m+[m[32m            return True[m
[32m+[m[32m    except (urlerror.URLError, TimeoutError, ValueError):[m
[32m+[m[32m        pass[m
[32m+[m
[32m+[m[32m    # Fallback: /health is more semantically precise but can be slower depending on persistence.[m
[32m+[m[32m    health_url = f"http://127.0.0.1:{p}/health"[m
[32m+[m[32m    try:[m
[32m+[m[32m        with urlrequest.urlopen(health_url, timeout=2.0) as resp:[m
[32m+[m[32m            if int(getattr(resp, "status", 0) or 0) != 200:[m
[32m+[m[32m                return False[m
[32m+[m[32m            body = resp.read(8192) or b""[m
[32m+[m[32m        text = body.decode("utf-8", errors="ignore")[m
[32m+[m[32m        return "\"status\"" in text and ("ok" in text or "degraded" in text)[m
[32m+[m[32m    except (urlerror.URLError, TimeoutError, ValueError):[m
[32m+[m[32m        return False[m
[32m+[m
[32m+[m
[32m+[m[32mdef _find_next_free_port(start_port: int, *, host: str = "127.0.0.1", tries: int = 30) -> int:[m
[32m+[m[32m    start = int(start_port)[m
[32m+[m[32m    for p in range(start, start + max(1, int(tries))):[m
[32m+[m[32m        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:[m
[32m+[m[32m            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)[m
[32m+[m[32m            try:[m
[32m+[m[32m                s.bind((host, p))[m
[32m+[m[32m                return p[m
[32m+[m[32m            except OSError:[m
[32m+[m[32m                continue[m
[32m+[m[32m    raise RuntimeError(f"No free port found in range [{start}, {start + tries})")[m
[32m+[m
[32m+[m
 def main() -> None:[m
     parser = argparse.ArgumentParser(description="Run Neraium demo (FastAPI + Next.js)")[m
     parser.add_argument("--backend-port", type=int, default=8000)[m
[36m@@ -61,38 +120,79 @@[m [mdef main() -> None:[m
     print("Neraium Demo — FastAPI + Next.js")[m
     print("=" * 70)[m
 [m
[31m-    backend_env = os.environ.copy()[m
[31m-    backend_env["PORT"] = str(args.backend_port)[m
[31m-[m
[31m-    backend_proc = subprocess.Popen([m
[31m-        [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", str(args.backend_port)],[m
[31m-        env=backend_env,[m
[31m-    )[m
[32m+[m[32m    backend_port = int(args.backend_port)[m
[32m+[m[32m    backend_proc: subprocess.Popen[bytes] | None = None[m
[32m+[m
[32m+[m[32m    # Backend: reuse if Neraium already running, otherwise pick a free port.[m
[32m+[m[32m    if _is_port_listening(backend_port):[m
[32m+[m[32m        if _probe_neraium_backend(backend_port):[m
[32m+[m[32m            print(f"Reusing existing Neraium backend at http://localhost:{backend_port}")[m
[32m+[m[32m        else:[m
[32m+[m[32m            new_port = _find_next_free_port(backend_port + 1)[m
[32m+[m[32m            print(f"Backend port {backend_port} is in use; switching to {new_port}.")[m
[32m+[m[32m            backend_port = int(new_port)[m
[32m+[m
[32m+[m[32m    if not _is_port_listening(backend_port):[m
[32m+[m[32m        backend_env = os.environ.copy()[m
[32m+[m[32m        backend_env["PORT"] = str(backend_port)[m
[32m+[m[32m        backend_proc = subprocess.Popen([m
[32m+[m[32m            [[m
[32m+[m[32m                sys.executable,[m
[32m+[m[32m                "-m",[m
[32m+[m[32m                "uvicorn",[m
[32m+[m[32m                "apps.api.main:app",[m
[32m+[m[32m                "--host",[m
[32m+[m[32m                "0.0.0.0",[m
[32m+[m[32m                "--port",[m
[32m+[m[32m                str(backend_port),[m
[32m+[m[32m            ],[m
[32m+[m[32m            env=backend_env,[m
[32m+[m[32m        )[m
[32m+[m
[32m+[m[32m    frontend_port = int(args.frontend_port)[m
     frontend_proc: subprocess.Popen[bytes] | None = None[m
 [m
     try:[m
         if args.backend_only:[m
[31m-            print(f"Backend running at http://localhost:{args.backend_port}")[m
[32m+[m[32m            print(f"Backend running at http://localhost:{backend_port}")[m
             print("Press Ctrl+C to stop.")[m
[31m-            backend_proc.wait()[m
[32m+[m[32m            if backend_proc is not None:[m
[32m+[m[32m                backend_proc.wait()[m
[32m+[m[32m            else:[m
[32m+[m[32m                while True:[m
[32m+[m[32m                    time.sleep(1.0)[m
             return[m
 [m
[32m+[m[32m        # Frontend: if already running, don't start a second instance.[m
[32m+[m[32m        if _is_port_listening(frontend_port):[m
[32m+[m[32m            print(f"Frontend already running at http://localhost:{frontend_port}")[m
[32m+[m[32m            print(f"Backend:  http://localhost:{backend_port}")[m
[32m+[m[32m            print("Press Ctrl+C to stop.")[m
[32m+[m[32m            while True:[m
[32m+[m[32m                if backend_proc is not None and backend_proc.poll() is not None:[m
[32m+[m[32m                    raise RuntimeError(f"Backend process exited unexpectedly (code={backend_proc.returncode}).")[m
[32m+[m[32m                time.sleep(0.5)[m
[32m+[m
         _ensure_frontend_dependencies()[m
         frontend_env = os.environ.copy()[m
[31m-        frontend_env["NEXT_PUBLIC_NERAIUM_API_BASE"] = f"http://localhost:{args.backend_port}"[m
[32m+[m[32m        frontend_env["NEXT_PUBLIC_NERAIUM_API_BASE"] = f"http://localhost:{backend_port}"[m
 [m
         npm = shutil.which("npm") or "npm"[m
[31m-        frontend_proc = subprocess.Popen([npm, "run", "dev", "--", "-p", str(args.frontend_port)], cwd=str(FRONTEND_DIR), env=frontend_env)[m
[31m-[m
[31m-        print(f"Backend:  http://localhost:{args.backend_port}")[m
[31m-        print(f"Frontend: http://localhost:{args.frontend_port}")[m
[32m+[m[32m        frontend_proc = subprocess.Popen([m
[32m+[m[32m            [npm, "run", "dev", "--", "-p", str(frontend_port)],[m
[32m+[m[32m            cwd=str(FRONTEND_DIR),[m
[32m+[m[32m            env=frontend_env,[m
[32m+[m[32m        )[m
[32m+[m
[32m+[m[32m        print(f"Backend:  http://localhost:{backend_port}")[m
[32m+[m[32m        print(f"Frontend: http://localhost:{frontend_port}")[m
         print("Press Ctrl+C to stop.")[m
 [m
         while True:[m
[31m-            if backend_proc.poll() is not None:[m
[31m-                raise RuntimeError("Backend process exited unexpectedly.")[m
[31m-            if frontend_proc and frontend_proc.poll() is not None:[m
[31m-                raise RuntimeError("Frontend process exited unexpectedly.")[m
[32m+[m[32m            if backend_proc is not None and backend_proc.poll() is not None:[m
[32m+[m[32m                raise RuntimeError(f"Backend process exited unexpectedly (code={backend_proc.returncode}).")[m
[32m+[m[32m            if frontend_proc is not None and frontend_proc.poll() is not None:[m
[32m+[m[32m                raise RuntimeError(f"Frontend process exited unexpectedly (code={frontend_proc.returncode}).")[m
             time.sleep(0.5)[m
 [m
     except KeyboardInterrupt:[m
[36m@@ -100,7 +200,10 @@[m [mdef main() -> None:[m
     finally:[m
         for proc in [frontend_proc, backend_proc]:[m
             if proc and proc.poll() is None:[m
[31m-                proc.send_signal(signal.SIGINT)[m
[32m+[m[32m                try:[m
[32m+[m[32m                    proc.terminate()[m
[32m+[m[32m                except Exception:[m
[32m+[m[32m                    pass[m
                 try:[m
                     proc.wait(timeout=5)[m
                 except subprocess.TimeoutExpired:[m
[1mdiff --git a/ui/app.py b/ui/app.py[m
[1mindex 8ab87e4a..7816744a 100644[m
[1m--- a/ui/app.py[m
[1m+++ b/ui/app.py[m
[36m@@ -1,4 +1,4 @@[m
[31m-from __future__ import annotations[m
[32m+[m[32m﻿from __future__ import annotations[m
 [m
 from html import escape[m
 import math[m
[36m@@ -260,8 +260,8 @@[m [mdef _render_gate_decision_html(gate_card: dict[str, Any]) -> str:[m
     transition_type = escape(str(gate_card.get("transition_type") or "STABLE"))[m
     risk_direction = escape(str(gate_card.get("risk_direction") or "UNCERTAIN"))[m
     ts_meta = str(gate_card.get("timestamp_display") or "").replace("Change evaluated at: ", "").strip()[m
[31m-    ts_display = escape(ts_meta) if ts_meta else "—"[m
[31m-    doctrine_version = escape(str(gate_card.get("doctrine_version") or "—"))[m
[32m+[m[32m    ts_display = escape(ts_meta) if ts_meta else "â€”"[m
[32m+[m[32m    doctrine_version = escape(str(gate_card.get("doctrine_version") or "â€”"))[m
     system_insights = gate_card.get("system_insights") if isinstance(gate_card.get("system_insights"), dict) else {}[m
 [m
     def _chip(label_text: str, value: str, accent_color: str) -> str:[m
[36m@@ -291,7 +291,7 @@[m [mdef _render_gate_decision_html(gate_card: dict[str, Any]) -> str:[m
             if not isinstance(metric, dict):[m
                 continue[m
             trend = metric.get("trend") if isinstance(metric.get("trend"), dict) else {}[m
[31m-            arrow = escape(str(trend.get("arrow") or "→"))[m
[32m+[m[32m            arrow = escape(str(trend.get("arrow") or "â†’"))[m
             trend_label = escape(str(trend.get("label") or "Stable"))[m
             mlabel = escape(str(metric.get("label") or "Metric"))[m
             mvalue = escape(str(metric.get("value") or "0"))[m
[36m@@ -299,12 +299,12 @@[m [mdef _render_gate_decision_html(gate_card: dict[str, Any]) -> str:[m
                 '<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;'[m
                 'border-bottom:1px solid rgba(148,163,184,0.14);">'[m
                 f'<span style="color:#cbd5e1;font-size:12px;">{mlabel}</span>'[m
[31m-                f'<span style="color:#f8fafc;font-size:12px;font-weight:700;">{arrow} {mvalue} · {trend_label}</span>'[m
[32m+[m[32m                f'<span style="color:#f8fafc;font-size:12px;font-weight:700;">{arrow} {mvalue} Â· {trend_label}</span>'[m
                 '</div>'[m
             )[m
[31m-        phase_context = escape(str(system_insights.get("phase_context") or "—"))[m
[31m-        timestamp_display = escape(str(system_insights.get("timestamp_display") or "—"))[m
[31m-        insight_text = escape(str(system_insights.get("insight_text") or "—"))[m
[32m+[m[32m        phase_context = escape(str(system_insights.get("phase_context") or "â€”"))[m
[32m+[m[32m        timestamp_display = escape(str(system_insights.get("timestamp_display") or "â€”"))[m
[32m+[m[32m        insight_text = escape(str(system_insights.get("insight_text") or "â€”"))[m
         decision_line = escape(str(system_insights.get("decision") or "Decision: Accepted"))[m
         transition_line = escape(str(system_insights.get("state_transition") or "State Transition: Confirmed"))[m
         insight_section = ([m
[36m@@ -463,9 +463,9 @@[m [mdef _render_system_geometry_html(system_zone: dict[str, Any]) -> str:[m
         '<h4>Interpretation</h4>'[m
         f'<ul>{trend_rows}</ul>'[m
         '<div class="ner-delta-row">'[m
[31m-        f'<span>ΔDrift {drift_delta:+.3f}</span>'[m
[31m-        f'<span>ΔStability {stability_delta:+.3f}</span>'[m
[31m-        f'<span>ΔCoherence {coherence_delta:+.3f}</span>'[m
[32m+[m[32m        f'<span>Î”Drift {drift_delta:+.3f}</span>'[m
[32m+[m[32m        f'<span>Î”Stability {stability_delta:+.3f}</span>'[m
[32m+[m[32m        f'<span>Î”Coherence {coherence_delta:+.3f}</span>'[m
         '</div>'[m
         '</div>'[m
     )[m
[36m@@ -474,7 +474,7 @@[m [mdef _render_system_geometry_html(system_zone: dict[str, Any]) -> str:[m
         f'<div class="ner-global-state-indicator" style="--state-accent:{state_accent};--state-bg:{state_bg};">'[m
         '<span class="ner-global-state-label">Overall System State</span>'[m
         f'<strong>{escape(global_state)}</strong>'[m
[31m-        f'<small>Confidence {confidence:.2f} • Drift {drift_intensity:.2%} • Coherence {coherence:.2%}</small>'[m
[32m+[m[32m        f'<small>Confidence {confidence:.2f} â€¢ Drift {drift_intensity:.2%} â€¢ Coherence {coherence:.2%}</small>'[m
         '</div>'[m
     )[m
 [m
[36m@@ -820,7 +820,7 @@[m [mdef _render_system_context_html(system_zone: dict[str, Any]) -> str:[m
         '<div class="ner-panel-head">'[m
         '<div style="display:flex;flex-direction:column;gap:2px;">'[m
         '<span class="ner-eyebrow">Replay telemetry</span>'[m
[31m-        f'<span style="font-size:12px;color:#7c8ba8;">Structural evolution across {point_count} frames · divergence and breakpoints emphasized</span>'[m
[32m+[m[32m        f'<span style="font-size:12px;color:#7c8ba8;">Structural evolution across {point_count} frames Â· divergence and breakpoints emphasized</span>'[m
         '</div>'[m
         '</div>'[m
     )[m
[36m@@ -1043,7 +1043,7 @@[m [mdef _load_unified_shell([m
     latest = records[-1] if records else {}[m
     timestamp = str(latest.get("timestamp", "")).replace("Z", "") if records else None[m
 [m
[31m-    facility_coherence = system_state.coherence if system_state else 0.75[m
[32m+[m[32m    facility_coherence = getattr(system_state, "coherence", 0.75) if system_state else 0.75[m
     rooms = build_facility_rooms_data(system_state, records)[m
     subsystems = build_subsystems_data(system_state, records)[m
     states_timeline = build_timeline_states(records)[m
[36m@@ -1073,6 +1073,7 @@[m [mdef _load_unified_shell([m
         records=records,[m
         no_action_projection=no_action_projection,[m
         no_action_consequence_insight=insights.get("no_action_consequence", ""),[m
[32m+[m[32m        recoverability_insight=insights.get("recoverability", ""),[m
     )[m
 [m
     return ([m
[36m@@ -1373,7 +1374,7 @@[m [mdef _render_replay_monitor([m
         f'<div class="ner-insight-state">{escape(state_label)}</div>'[m
         f'<div class="ner-insight-grid"><span>Structural Drift</span><strong>{active_drift:.3f}</strong>'[m
         f'<span>Relational Instability</span><strong>{active_instability:.3f}</strong>'[m
[31m-        f'<span>Timestamp</span><strong>{escape(str(current_frame_state.get("timestamp") or "—"))}</strong>'[m
[32m+[m[32m        f'<span>Timestamp</span><strong>{escape(str(current_frame_state.get("timestamp") or "â€”"))}</strong>'[m
         f'<span>Confidence</span><strong>{confidence:.2f}</strong>'[m
         f'<span>Trend</span><strong>{escape(trend_label)}</strong>'[m
         f'<span>Phase</span><strong>{escape(phase)}</strong></div>'[m
[36m@@ -1383,7 +1384,7 @@[m [mdef _render_replay_monitor([m
     status_html = ([m
         '<div class="ner-status-bar">'[m
         '<div class="ner-status-left"><span class="ner-wordmark">NERAIUM</span><span class="ner-status-sub">Live System Replay</span></div>'[m
[31m-        f'<div class="ner-status-center">{escape(str(current.get("asset_id") or "Unknown Asset"))} · Frame {idx} / {len(rows)}</div>'[m
[32m+[m[32m        f'<div class="ner-status-center">{escape(str(current.get("asset_id") or "Unknown Asset"))} Â· Frame {idx} / {len(rows)}</div>'[m
         f'<div class="ner-status-right"><span class="ner-pill ner-pill-state">{escape(state_label)}</span>'[m
         f'<span class="ner-pill">Confidence {confidence:.2f}</span></div></div>'[m
     )[m
[36m@@ -1639,7 +1640,7 @@[m [mdef create_gradio_app():[m
 [m
             bottom_timeline = gr.HTML(value=initial_bottom_timeline, elem_classes=["ner-state-timeline-container"])[m
 [m
[31m-        with gr.Group(label="Classic Operations View"):[m
[32m+[m[32m        with gr.Group():[m
             status = gr.HTML(value=initial_status)[m
         with gr.Row(elem_classes=["ner-main-content-row"]):[m
             chart = gr.HTML(value=initial_chart, scale=3)[m
[36m@@ -1713,3 +1714,5 @@[m [mdef create_gradio_app():[m
                                                       top_bar, system_field, left_panel, right_panel, bottom_timeline])[m
 [m
     return app[m
[41m+[m
[41m+[m
[1mdiff --git a/ui/components/system_field_coherence.py b/ui/components/system_field_coherence.py[m
[1mindex f51ab80a..4bcb9927 100644[m
[1m--- a/ui/components/system_field_coherence.py[m
[1m+++ b/ui/components/system_field_coherence.py[m
[36m@@ -1,4 +1,4 @@[m
[31m-"""System Field with Coherence Core.[m
[32m+[m[32m﻿"""System Field with Coherence Core.[m
 [m
 The heart of the Neraium operational interface:[m
 - Dynamic tetrahedral structure representing subsystem relationships[m
[36m@@ -157,12 +157,14 @@[m [mdef _compute_tetrahedron_geometry([m
     coherence_ring = {[m
         "radius": 0.65,[m
         "is_stable": state == "stable",[m
[31m-        "deformation": clamp(deformation, 0.0, 0.3),[m
[32m+[m[32m        "deformation": clamp(total_deformation, 0.0, 0.3),[m
         "glow_color": tension_color,[m
         "glow_intensity": 0.4 + (1.0 - coherence) * 0.6,[m
         "opacity": 0.5 + (coherence * 0.5),[m
     }[m
 [m
[32m+[m[32m    core_radius = 0.14 + 0.10 * clamp(coherence, 0.0, 1.0)[m
[32m+[m
     core_tightening = core_resistance * 2.0[m
     effective_core_radius = max(0.06, core_radius - core_tightening)[m
 [m
[36m@@ -635,3 +637,6 @@[m [mdef render_system_field_svg([m
     svg_parts.append("</svg>")[m
 [m
     return "\n".join(svg_parts)[m
[41m+[m
[41m+[m
[41m+[m
[1mdiff --git a/ui/layouts/unified_app_shell.py b/ui/layouts/unified_app_shell.py[m
[1mindex e31e0993..4162723f 100644[m
[1m--- a/ui/layouts/unified_app_shell.py[m
[1m+++ b/ui/layouts/unified_app_shell.py[m
[36m@@ -1,15 +1,15 @@[m
[31m-"""Unified App Shell: System-first architecture.[m
[32m+[m[32m﻿"""Unified App Shell: System-first architecture.[m
 [m
 The complete operational surface unified as one connected canvas:[m
 [m
 AppShell[m
[31m-├─ TopStatusBar (Facility Command Strip)[m
[31m-├─ MainCanvas (central focus)[m
[31m-│  ├─ SystemField (dominant, interactive tetrahedron with coherence core)[m
[31m-│  └─ OverlayLayer[m
[31m-│     ├─ SubsystemInfluence (left, floating)[m
[31m-│     └─ IntelligenceRail (right, floating)[m
[31m-└─ StateTimeline (bottom, integrated)[m
[32m+[m[32mâ”œâ”€ TopStatusBar (Facility Command Strip)[m
[32m+[m[32mâ”œâ”€ MainCanvas (central focus)[m
[32m+[m[32mâ”‚  â”œâ”€ SystemField (dominant, interactive tetrahedron with coherence core)[m
[32m+[m[32mâ”‚  â””â”€ OverlayLayer[m
[32m+[m[32mâ”‚     â”œâ”€ SubsystemInfluence (left, floating)[m
[32m+[m[32mâ”‚     â””â”€ IntelligenceRail (right, floating)[m
[32m+[m[32mâ””â”€ StateTimeline (bottom, integrated)[m
 [m
 NO boxed layout.[m
 NO panel-based dashboard.[m
[36m@@ -51,6 +51,7 @@[m [mdef build_unified_app_shell([m
     records: list[dict[str, Any]] | None = None,[m
     no_action_projection: list[dict[str, Any]] | None = None,[m
     no_action_consequence_insight: str = "",[m
[32m+[m[32m    recoverability_insight: str = "",[m
 ) -> dict[str, str]:[m
     """Build the unified app shell.[m
 [m
[36m@@ -81,9 +82,9 @@[m [mdef build_unified_app_shell([m
     states_timeline = states_timeline or [][m
     critical_alerts = critical_alerts or [][m
 [m
[31m-    coherence = state.coherence if state else 0.7[m
[32m+[m[32m    coherence = getattr(state, "coherence", 0.75)[m
     drift = state.drift_intensity if state else 0.2[m
[31m-    stability = state.stability if state else 0.8[m
[32m+[m[32m    stability = getattr(state, "stability", 0.8)[m
 [m
     system_state = "stable"[m
     if drift > 0.6:[m
[36m@@ -130,7 +131,7 @@[m [mdef build_unified_app_shell([m
         critical_alerts=critical_alerts if critical_alerts else None,[m
         coherence_score=coherence,[m
         no_action_consequence=no_action_consequence_insight,[m
[31m-        recoverability_context=insights.get("recoverability", ""),[m
[32m+[m[32m        recoverability_context=recoverability_insight,[m
     )[m
 [m
     bottom_timeline_html = render_state_timeline([m
[36m@@ -148,3 +149,6 @@[m [mdef build_unified_app_shell([m
         "right_panel": right_panel_html,[m
         "bottom_timeline": bottom_timeline_html,[m
     }[m
[41m+[m
[41m+[m
[41m+[m
[1mdiff --git a/ui/unified_shell_data.py b/ui/unified_shell_data.py[m
[1mindex 28eab82c..2efd5216 100644[m
[1m--- a/ui/unified_shell_data.py[m
[1m+++ b/ui/unified_shell_data.py[m
[36m@@ -1,4 +1,4 @@[m
[31m-"""Helper to generate data for the unified app shell from system state.[m
[32m+[m[32m﻿"""Helper to generate data for the unified app shell from system state.[m
 [m
 Converts SystemState and related data into the format expected by[m
 unified shell components (facility command strip, subsystems, timeline, intelligence).[m
[36m@@ -199,8 +199,8 @@[m [mdef build_subsystems_data([m
     subsystems = [][m
 [m
     drift = system_state.drift_intensity if system_state else 0.2[m
[31m-    stability = system_state.stability if system_state else 0.8[m
[31m-    coherence = system_state.coherence if system_state else 0.75[m
[32m+[m[32m    stability = getattr(system_state, "stability", 0.8) if system_state else 0.8[m
[32m+[m[32m    coherence = getattr(system_state, "coherence", 0.75) if system_state else 0.75[m
 [m
     climate_drift_contrib = drift * 30[m
     climate_fragility = (climate_drift_contrib / 100) * (1.0 - coherence)[m
[36m@@ -208,7 +208,7 @@[m [mdef build_subsystems_data([m
         {[m
             "subsystem_id": "climate",[m
             "subsystem_name": "Climate",[m
[31m-            "condition": f"{22 + drift * 5:.1f}°C",[m
[32m+[m[32m            "condition": f"{22 + drift * 5:.1f}Â°C",[m
             "behavioral_state": "Stabilizing" if stability > 0.6 else "Drifting",[m
             "drift_contribution_pct": climate_drift_contrib,[m
             "confidence_pct": (1.0 - drift) * 100,[m
[36m@@ -283,7 +283,7 @@[m [mdef build_timeline_states([m
     if not records or len(records) == 0:[m
         return [[m
             {[m
[31m-                "timestamp": "—",[m
[32m+[m[32m                "timestamp": "â€”",[m
                 "state_label": "baseline",[m
                 "coherence": 0.85,[m
                 "drift": 0.1,[m
[36m@@ -292,12 +292,11 @@[m [mdef build_timeline_states([m
                 "emphasis": "low",[m
             }[m
         ][m
[31m-[m
     states = [][m
     for i, record in enumerate(records[-24:]):[m
         drift = float(record.get("structural_drift_score", 0.2))[m
         stability = float(record.get("relational_stability_score", 0.8))[m
[31m-        coherence = float(record.get("coherence_score", 0.75))[m
[32m+[m[32m        coherence = float(record.get("coherence", 0.75) or 0.75)[m
 [m
         if drift > 0.6:[m
             state_label = "critical"[m
[36m@@ -312,7 +311,7 @@[m [mdef build_timeline_states([m
 [m
         emphasis = "high" if bool(record.get("event_admitted")) else "medium" if drift > 0.15 else "low"[m
 [m
[31m-        timestamp = str(record.get("timestamp", "")).split("T")[-1] if record.get("timestamp") else "—"[m
[32m+[m[32m        timestamp = str(record.get("timestamp", "")).split("T")[-1] if record.get("timestamp") else "â€”"[m
 [m
         states.append([m
             {[m
[36m@@ -388,8 +387,9 @@[m [mdef build_intelligence_insights([m
         Dictionary with insight keys including no-action consequence[m
     """[m
     drift = system_state.drift_intensity if system_state else 0.2[m
[31m-    stability = system_state.stability if system_state else 0.8[m
[31m-    coherence = system_state.coherence if system_state else 0.75[m
[32m+[m[32m    stability = getattr(system_state, "stability", 0.8) if system_state else 0.8[m
[32m+[m[32m    coherence = getattr(system_state, "coherence", 0.75) if system_state else 0.75[m
[32m+[m
 [m
     gate_decision = gate_decision or {}[m
     decision = str(gate_decision.get("decision", "SUPPRESS")).upper()[m
[36m@@ -431,7 +431,7 @@[m [mdef build_intelligence_insights([m
         driver = "All subsystem couplings stable; coherent equilibrium maintained"[m
 [m
     if decision == "ADMIT":[m
[31m-        focus = "⚠️ CRITICAL: Structural transition admitted. Execute intervention protocol immediately."[m
[32m+[m[32m        focus = "âš ï¸ CRITICAL: Structural transition admitted. Execute intervention protocol immediately."[m
     elif drift > 0.3:[m
         if minutes_to_escalation and minutes_to_escalation < 30:[m
             focus = f"Escalation within {minutes_to_escalation} minutes. Intervention needed now."[m
[36m@@ -512,12 +512,17 @@[m [mdef get_critical_alerts([m
     if drift > 0.5:[m
         alerts.append("High structural drift. Recovery path becoming constrained.")[m
 [m
[31m-    stability = system_state.stability if system_state else 0.8[m
[32m+[m[32m    stability = getattr(system_state, "stability", 0.8) if system_state else 0.8[m
     if stability < 0.3:[m
         alerts.append("Relational stability critically low. Subsystem coupling degraded.")[m
 [m
[31m-    coherence = system_state.coherence if system_state else 0.75[m
[32m+[m[32m    coherence = getattr(system_state, "coherence", 0.75) if system_state else 0.75[m
     if coherence < 0.4:[m
         alerts.append("System coherence below operational threshold. Imminent structural failure risk.")[m
 [m
     return alerts[m
[41m+[m
[41m+[m
[41m+[m
[41m+[m
[41m+[m
