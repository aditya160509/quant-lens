# Quant360 Deep-Scan Audit Supplement (Phase 2)

**Focus**: Frontend Integrity, AI/ML Infrastructure, and Deployment Readiness

## 🔍 NEW ARCHITECTURAL FINDINGS

### 12. Configuration Failures (CRITICAL)

- **Localhost Dependency**: 78+ instances of `http://localhost:8000` found in `frontend/src`.
- **Finding**: Hardcoded strings in `OrderPanel.tsx`, `TerminalOverlay.jsx`, and `lib/api.js`.
- **Risk**: The application is "Deployment-Locked." It will fail in any environment (Staging/Prod) where the API is not on the same local loopback.

### 23. AI Specific Architecture Failures (HIGH)

- **Lexicon vs. Model**: `sentiment_analyzer.py` claims "FinBERT Tier" accuracy but only implements a manual keyword dictionary (`VADER_LEXICON`).
- **Hallucinated Sophistication**: The system serves "Sentiment Momentum" and "Divergence" based on a rigid list of words (e.g., "beat" = 2.0).
- **Risk**: Financial context is lost. "Company's earnings were not a beat" would be scored as POSITIVE by the simplified parser because "beat" is positive, ignoring the negation context at scale.

### 4. Scalability & 8. Consistency (HIGH)

- **Instance-Locked ML Training**: `ml_api.py` uses `_training_lock = threading.Lock()` and `_training_status = {}`.
- **Split Brain**: If Instance A is training a Random Forest model, Instance B has no knowledge of it. A user might see "Training..." on one page refresh and "No Model Found" on the next.
- **Solution Required**: Redis-backed state for training status.

### 11. Deployment Failures (MEDIUM)

- **Factor Data Vacuum**: `factors_intelligence.py` refers to local `.csv` files for Fama-French factors but has no fallback to download them.
- **Finding**: Line 21 mentions "Kenneth French direct download," but no code exists to perform this if `data/factors_us` is empty.
- **Risk**: Fresh CI/CD deployments will crash or serve empty "0.0" risk metrics.

### 21. Cost Failures (LOW-MEDIUM)

- **Unbounded PCA Rolling**: `pca_god_mode.py` performs 25+ Eigendecompositions per request for "Rolling Stability" analysis.
- **Metric**: 50 assets \* 25 windows = 1,250 heavy matrix operations.
- **Risk**: Multiple concurrent users can lock up the CPU threads, leading to a "Denial of Wallet/Service" (DoW/DoS) in cloud environments like AWS Lambda or Fargate.

## 🛠️ MITIGATION CHECKLIST

- [ ] **centralize_apis**: Move all `localhost` calls to `process.env.NEXT_PUBLIC_API_URL`.
- [ ] **bootstrap_data**: Add a startup script to fetch necessary CSVs from Ken French / Yahoo Finance.
- [ ] **global_state_proxy**: Replace `_training_status` dict with a Supabase or Redis KV store.
- [ ] **request_bounding**: Add `max_assets` and `max_windows` constraints to the PCA engine.
- [ ] **robust_sentiment**: Integrate a true HuggingFace `transformers` pipeline or a reliable external API (e.g., SentimentInvestor).

---

**Audit Rating (Phase 2)**: ⚠️ **STABILITY WARNING**
The system is functionally impressive but architecturally a "Local Research" project. Significant refactoring of configuration and state is required before institutional production.
