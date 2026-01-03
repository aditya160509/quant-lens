# QUANT360 ML GOD STACK — COMPLETE SPECIFICATION FOR IMPLEMENTATION

## EXECUTIVE SUMMARY

You are building an **institutional-grade quantitative trading platform** with machine learning capabilities that rival Bloomberg Terminal, FactSet, and proprietary hedge fund systems. This is not a toy dashboard—this is a **production-ready ML infrastructure** for professional traders, portfolio managers, and quant researchers.

The system has **15 integrated ML modules** organized into **6 capability levels**, from raw data processing to executive decision support. Every module has been architected with **clear inputs, outputs, models, and UI placement**. The frontend is split between **actionable portfolio tools** and **diagnostic research labs**.

This specification provides everything needed to build the complete system: data flows, ML model selection, UI/UX requirements, feature descriptions, and integration patterns.

---

## ARCHITECTURAL PRINCIPLES

### Navigation Structure (CRITICAL)

**Portfolio Section** — Actionable surfaces where users make decisions:

- `/portfolio/signals` — Signal analysis, ML confidence, recommendations
- `/portfolio/diversification` — Asset clustering and redundancy detection
- `/portfolio/risk` — Position sizing and risk management

**Labs Research Section** — Analytical and diagnostic tools:

- `/labs/research/ml/data` — Dataset construction and validation
- `/labs/research/ml/analysis` — Conditional performance analysis
- `/labs/research/ml/explain` — Feature attribution and explainability
- `/labs/research/ml/monitoring` — Model drift and decay tracking
- `/labs/research/ml/errors` — Failure analysis and error clustering
- `/labs/research/ml/embedding` — Dimensionality reduction visualization
- `/labs/research/regimes` — Market regime discovery
- `/labs/research/strategies` — Strategy overlap detection

**Backend API Layer** (not user-facing):

- `/backend/quant/ml/*` — Model training, inference, storage

### Design Philosophy

1. **Institutional Quality**: Every chart, table, and visualization must match or exceed Bloomberg/FactSet standards
2. **Speed First**: All interactions feel instant; use loading skeletons, progressive loading, and optimistic updates
3. **Data Density**: Pack maximum information without clutter—traders value information density
4. **Explainability**: Every ML prediction must be explainable and traceable
5. **Trust Through Transparency**: Show confidence intervals, model disagreement, historical accuracy
6. **Professional Aesthetics**: Dark theme default, muted colors, clear typography, no childish elements

---

## LEVEL 1 — DATA & TRUTH LAYER

**Philosophy**: If the foundation data is wrong, every ML model built on it is worthless. This layer ensures data quality, proper labeling, and feature engineering integrity.

---

### MODULE 1: Signal Outcome Dataset Builder

**Purpose**: Transform raw trading signals into machine learning training data with proper labels and features.

**Business Logic**:

- Takes historical trading signals (buy/sell triggers) and converts them into labeled examples
- Each row represents one signal occurrence with its outcome (success/failure)
- Labels can be binary (worked/didn't work), continuous (return %), or risk-adjusted (Sharpe)
- Must handle different exit rules: fixed time horizon, stop loss, take profit, trailing stop
- Must align features temporally to avoid look-ahead bias

**Input Data Requirements**:

- **Signal Metadata**: Signal ID, signal name, strategy name, generation timestamp
- **Entry/Exit Info**: Entry price, entry timestamp, exit price, exit timestamp, exit reason
- **Market Data**: OHLCV data for the asset at signal time
- **Volatility Metrics**: ATR (Average True Range), Bollinger Band width, historical volatility
- **Market Context**: Current market regime label, VIX level, market breadth indicators
- **Corporate Events**: Days until next earnings, dividend dates, stock split flags
- **Breadth Indicators**: Advance/decline ratio, new highs/lows, sector rotation metrics

**Output Data**:

- **Feature Matrix X**: Rows = signals, Columns = engineered features (normalized, lagged)
- **Label Vector y**: Target variable (binary success, return %, Sharpe ratio)
- **Metadata DataFrame**: Signal ID, timestamps, asset, strategy, for tracking and debugging

**ML Models Used**: None (pure data transformation)

**UI Requirements** (`/labs/research/ml/data`):

**Primary View: Dataset Overview Table**

- Scrollable table showing first 100 rows of dataset
- Columns: Signal ID, Asset, Entry Date, Exit Date, Return %, Label, Regime, Volatility Bucket
- Sortable by any column
- Filter controls: Date range, strategy, asset, regime type
- Export button for CSV download
- Stats summary bar showing total signals, win rate, average return

**Secondary View: Label Balance Visualization**

- Horizontal bar chart showing distribution of labels (if binary: wins vs losses)
- If continuous labels: histogram of return distribution
- Color coded: green for positive, red for negative
- Percentage annotations on bars

**Tertiary View: Missing Data Heatmap**

- Grid visualization where rows = signals, columns = features
- Color intensity shows missing data (white = complete, dark red = missing)
- Hover tooltip showing exact missing percentage per feature
- Clickable cells to drill into specific missing data patterns

**Key Interactions**:

- Click any row to see full signal details in modal
- Toggle between binary/continuous label view
- Regenerate dataset with different labeling rules (button)
- Mark problematic signals for exclusion

---

### MODULE 2: Feature Engineering & Validation Engine

**Purpose**: Create ML-ready features from raw indicators, ensuring no data leakage and proper normalization.

**Business Logic**:

- Apply lag windows to prevent look-ahead bias (e.g., use yesterday's indicator, not today's)
- Normalize features using appropriate methods (z-score, min-max, rank-based)
- Create interaction features (e.g., momentum × volatility)
- Detect and flag features with suspicious properties (100% correlation, constant values)
- Version control for features (track what features were used in which model version)

**Input Data Requirements**:

- **Raw Indicators**: RSI, MACD, moving averages, volume indicators, Bollinger Bands
- **Configuration**: Lag periods (1-day, 5-day, 20-day), normalization method per feature
- **Historical Data**: Sufficient history for calculating rolling statistics

**Output Data**:

- **ML-Ready Feature Store**: Normalized, lagged feature matrix ready for model training
- **Feature Metadata**: Feature names, creation date, normalization method, lag applied
- **Versioned Feature Sets**: Named snapshots of feature configurations (e.g., "v1.0_baseline", "v2.1_with_breadth")

**ML Models Used**: None (statistical transformations only)

**UI Requirements**: Internal only—no dedicated UI. Accessed programmatically or via admin panel.

**Configuration Interface** (if built):

- List of available raw indicators with checkboxes
- Lag window selector (dropdown: 0, 1, 5, 10, 20 days)
- Normalization method dropdown per feature (z-score, min-max, rank, log)
- "Build Feature Set" button
- Version naming and tagging system

**Validation Dashboard** (optional advanced feature):

- Feature correlation heatmap showing inter-feature correlations
- Flag features with >0.95 correlation in red
- Feature stability chart: line plot showing feature mean/std over rolling windows
- Leakage detection report: statistical tests for look-ahead bias

---

## LEVEL 2 — SIGNAL INTELLIGENCE

**Philosophy**: This is where users see immediate value—ML models that predict which signals will work and under what conditions.

---

### MODULE 3: Signal Success Probability Engine

**Purpose**: For any current trading signal, predict the probability it will be profitable based on historical patterns and current market context.

**Business Logic**:

- Train classification models on historical signal outcomes
- For each new signal, extract current features and predict success probability
- Return not just a probability, but a confidence tier (high/medium/low confidence)
- Generate expected return distribution (e.g., "70% chance of 2-5% gain")
- Rank all active signals by predicted success probability

**Input Data Requirements**:

- **Feature Matrix**: From Module 2, current market features for the signal
- **Historical Outcomes**: Labeled dataset from Module 1
- **Current Regime Context**: Current market regime label (bull/bear/neutral/volatile)
- **Signal Metadata**: What strategy generated it, asset characteristics

**Output Data**:

- **Success Probability**: 0-100% probability the signal will be profitable
- **Confidence Tier**: "High" (model very certain), "Medium" (moderate agreement), "Low" (high uncertainty)
- **Expected Return Distribution**: Probability distribution of possible outcomes (e.g., 10% chance -5%, 30% chance 0-2%, 60% chance 2-10%)
- **Feature Contributions**: Which features most influenced this prediction (top 5)

**ML Models Used**:

1. **Logistic Regression**: Baseline, interpretable, fast
2. **Random Forest**: Handles non-linear relationships, provides feature importance
3. **XGBoost**: Best performance, captures complex interactions

**Model Training Strategy**:

- Use time-series cross-validation (no future data in training)
- Train all three models and ensemble their predictions
- Retrain weekly on expanding window (keep all historical data)
- Hyperparameter tuning via grid search on validation set

**UI Requirements** (`/portfolio/signals`):

**Primary View: Signal Ranking Table**

- Real-time table of all active signals with ML predictions
- Columns:
  - Asset (e.g., "AAPL", "SPY")
  - Signal Name (e.g., "Golden Cross", "RSI Oversold")
  - Entry Price
  - **Success Probability** (large, color-coded: >70% green, 50-70% yellow, <50% red)
  - Confidence Tier (badge: "High", "Medium", "Low")
  - Expected Return (e.g., "+3.2% ± 1.5%")
  - Top Contributing Feature (e.g., "Low volatility" or "Strong momentum")
- Sortable by probability (default sort)
- Filter: Show only high confidence, specific strategies, specific assets
- Clicking row expands to full detail card

**Expanded Detail Card** (slides out from right):

- Large probability gauge (circular, 0-100%)
- Confidence tier badge
- Expected return distribution: histogram showing probability of different return buckets
- Top 5 contributing features: horizontal bar chart with positive/negative contributions
- Historical context: "This signal has worked 68% of the time in similar conditions"
- Similar past signals: mini-table showing 3-5 most similar historical signals and their outcomes
- Action buttons: "Add to Watchlist", "Set Alert", "View Full Analysis"

**Secondary View: Probability Histogram**

- Distribution of success probabilities across all current signals
- X-axis: Probability bins (0-10%, 10-20%, ..., 90-100%)
- Y-axis: Number of signals
- Shows where most signals cluster
- Identifies if current market has many high-confidence opportunities or not

**Tertiary View: Model Performance Metrics**

- Precision-Recall Curve: Shows model tradeoff between catching winners and avoiding false positives
- Confusion Matrix: True positives, false positives, true negatives, false negatives (last 30 days)
- Rolling Accuracy Chart: Line chart showing model accuracy over time
- Per-Strategy Breakdown: Table showing model performance for each strategy type

**Key Interactions**:

- Hover over any probability to see confidence interval (e.g., "67% ± 8%")
- Click "Why?" button next to probability to see feature attribution (links to Module 6)
- Set alert: "Notify me when high-confidence signals appear"
- Bulk actions: Select multiple signals, "Add all to portfolio", "Export selection"

---

### MODULE 4: Conditional Performance Analyzer

**Purpose**: Understand when and why signals work—break down performance by market regime, volatility, sector rotation, and other conditions.

**Business Logic**:

- Group historical signals by contextual variables (regime, volatility quartile, market direction)
- Calculate performance metrics within each group (win rate, average return, Sharpe)
- Identify conditions where signals consistently outperform or underperform
- Provide "performance fingerprint" for each signal type

**Input Data Requirements**:

- **Signal Outcomes**: Historical returns from Module 1
- **Regime Labels**: Market regime at time of each signal (bull, bear, neutral, high vol)
- **Volatility States**: VIX level, ATR percentile at signal time
- **Market Direction**: Trend direction (uptrend, downtrend, sideways)
- **Sector Context**: Sector rotation indicator, leadership/laggard status

**Output Data**:

- **Conditional Return Matrix**: Rows = signal types, Columns = conditions, Cells = average return
- **Win Rate by Condition**: Percentage of winning trades in each market context
- **Best/Worst Conditions**: Ranked list of conditions where signal excels or fails

**ML Models Used**: Statistical aggregation (groupby, mean, std), no ML models

**UI Requirements** (`/labs/research/ml/analysis`):

**Primary View: Regime vs Return Heatmap**

- Heatmap where:
  - Rows = Signal types (RSI Oversold, MACD Cross, Breakout, etc.)
  - Columns = Market regimes (Bull Low Vol, Bull High Vol, Bear Low Vol, Bear High Vol, Neutral)
  - Cell color = Average return (green gradient for positive, red for negative)
  - Cell annotation = Return % and win rate (e.g., "+4.2% (72%)")
- Hover tooltip shows additional stats: sample size, Sharpe ratio, max drawdown
- Color scale clearly defined in legend
- Ability to filter by date range

**Secondary View: Conditional Win Rate Table**

- Sortable table with columns:
  - Signal Name
  - Overall Win Rate
  - Bull Market Win Rate
  - Bear Market Win Rate
  - High Vol Win Rate
  - Low Vol Win Rate
  - Best Condition (text, e.g., "Bull + Low Vol")
  - Worst Condition
- Color coding: >60% green, 40-60% yellow, <40% red
- Export to CSV button

**Tertiary View: Drawdown by Condition**

- Series of mini line charts, one per condition
- Each chart shows equity curve of signals fired in that condition
- Clearly marks maximum drawdown periods
- Allows comparison: "In bear markets, this signal has 15% max drawdown vs 8% in bull markets"

**Key Interactions**:

- Click any heatmap cell to drill down to individual signals in that condition
- Toggle between "Return", "Win Rate", "Sharpe Ratio" views
- Filter: "Show only high-frequency signals" (>50 samples)
- Compare mode: Select two conditions and see side-by-side comparison

---

### MODULE 5: Model Consensus & Disagreement Engine

**Purpose**: Combine predictions from multiple ML models to produce a robust, ensemble probability. Flag when models disagree (indicating uncertainty).

**Business Logic**:

- Train multiple diverse models (Logistic, Random Forest, XGBoost, LightGBM)
- For each signal, collect predictions from all models
- Calculate consensus probability (weighted average based on historical model accuracy)
- Calculate disagreement score (standard deviation of model predictions)
- High disagreement = low confidence, even if average probability is high

**Input Data Requirements**:

- **Predictions from Each Model**: Probability outputs from Logistic Regression, Random Forest, XGBoost, LightGBM
- **Historical Model Accuracy**: Per-model precision, recall, F1 score on validation set

**Output Data**:

- **Consensus Probability**: Weighted average of all model predictions (0-100%)
- **Disagreement Score**: Measure of prediction variance (0 = perfect agreement, 100 = maximum disagreement)
- **Per-Model Predictions**: Individual probabilities from each model for transparency

**ML Models Used**:

1. **Random Forest**: 500 trees, max depth 10
2. **XGBoost**: 300 rounds, learning rate 0.05
3. **LightGBM**: 500 iterations, gradient-based boosting

**Ensemble Strategy**:

- Weighted average where weights = model accuracy on most recent 1000 predictions
- If disagreement > 20%, downgrade confidence tier regardless of probability

**UI Requirements** (`/portfolio/signals`):

**Integrated into Module 3 Signal Table**:

- Add "Consensus" column showing final weighted probability
- Add "Model Agreement" column: visual indicator (🟢 high agreement, 🟡 medium, 🔴 disagreement)

**Expanded Detail View: Model Breakdown Panel**

- Horizontal stacked bar showing each model's prediction
- Bar segments colored by model: Logistic (blue), RF (green), XGBoost (orange), LightGBM (purple)
- Each segment length = model's probability
- Hover tooltip: "Random Forest: 73% (weighted 0.3 based on 82% accuracy)"
- Disagreement meter below: "Model Disagreement: 18% (Medium confidence)"

**Secondary View: Model Agreement Heatmap**

- Grid where rows = signals, columns = models
- Cell color = probability predicted by that model for that signal
- Visually shows where models agree (all cells same color) vs disagree (mixed colors)
- Filter: "Show only high disagreement signals"

**Tertiary View: Historical Model Accuracy Comparison**

- Line chart with multiple lines, one per model
- Y-axis: Rolling 30-day accuracy
- X-axis: Time
- Shows which models have been most reliable recently
- Table below: Per-model precision, recall, F1 for last 30, 90, 180 days

**Key Interactions**:

- Toggle individual models on/off in ensemble (recalculates consensus live)
- Click model name to see that model's feature importance
- "Trust this model more" button: increases weight manually (advanced users)

---

## LEVEL 3 — EXPLAINABILITY & FAILURE ANALYSIS

**Philosophy**: ML predictions without explanations are not actionable for professionals. This level makes models transparent and debuggable.

---

### MODULE 6: Feature Attribution Suite

**Purpose**: Explain why a model made a specific prediction by showing which features contributed most.

**Business Logic**:

- Use SHAP (SHapley Additive exPlanations) values to attribute prediction to features
- Global importance: Which features matter most across all predictions
- Local importance: Which features mattered for this specific signal
- Show direction: Did high RSI push probability up or down?

**Input Data Requirements**:

- **Trained Model**: Model object (XGBoost, Random Forest, etc.)
- **Feature Values**: Current feature values for the signal being explained
- **Background Dataset**: Representative sample for SHAP calculations

**Output Data**:

- **Global Feature Importance**: Ranked list of features by average impact on predictions
- **Per-Signal Attribution**: For any specific signal, breakdown of feature contributions
- **Contribution Direction**: Each feature's positive or negative influence

**ML Models Used**:

- **SHAP Explainer**: TreeExplainer for tree-based models, KernelExplainer for others

**UI Requirements** (`/labs/research/ml/explain`):

**Primary View: Global Feature Importance Bar Chart**

- Horizontal bar chart, bars sorted by importance (highest at top)
- Top 20 features shown
- X-axis: SHAP value magnitude (importance)
- Color coded: Blue bars
- Hover tooltip: "RSI_14: Average impact of 0.08 on probability"
- Toggle: "Show all features" expands to full list

**Secondary View: Per-Signal Waterfall Plot**

- Signal selector dropdown at top
- Waterfall chart showing:
  - Starting point: Base probability (e.g., 50%)
  - Each feature bar adds or subtracts probability
  - Arrows connecting bars showing cumulative effect
  - Final bar: Predicted probability
- Features sorted by absolute contribution
- Color: Green for positive contribution, red for negative
- Example: RSI (+12%) → Momentum (+8%) → Volatility (-5%) → Final: 65%

**Tertiary View: Feature Impact Summary Table**

- Table with columns:
  - Feature Name
  - Current Value (for this signal)
  - Typical Value (median across all signals)
  - Contribution to Prediction (e.g., "+12%")
  - Direction (↑ increases probability or ↓ decreases)
- Sortable by contribution magnitude
- Color coded rows

**Quaternary View: Feature Dependence Plots**

- Scatter plots showing how feature value affects prediction
- X-axis: Feature value (e.g., RSI from 0-100)
- Y-axis: SHAP value (contribution to prediction)
- Each dot = one historical signal
- Color = Another feature (to show interactions)
- Example: "When RSI is high, does volatility matter more?"
- Select from dropdown which feature to plot

**Key Interactions**:

- Click any feature in global importance to see its dependence plot
- "Explain this signal" button from Module 3 opens this page with signal pre-selected
- Download attribution report as PDF
- Compare attributions: Select two signals and see side-by-side waterfalls

---

### MODULE 7: Model Drift & Decay Monitor

**Purpose**: Detect when model performance degrades over time due to changing market conditions (concept drift) or feature distributions shifting.

**Business Logic**:

- Continuously track model accuracy on new predictions vs actual outcomes
- Monitor feature distributions: Are features shifting outside training range?
- Detect concept drift: Are relationships between features and outcomes changing?
- Generate alerts when performance drops below threshold or drift detected

**Input Data Requirements**:

- **Rolling Predictions**: Model predictions over time with timestamps
- **Realized Outcomes**: Actual results once signals have played out
- **Feature Distributions**: Current vs historical feature statistics (mean, std, percentiles)

**Output Data**:

- **Drift Score**: 0-100 metric indicating severity of distribution shift
- **Performance Decay Alerts**: Flags when accuracy drops significantly
- **Feature Drift Heatmap**: Which features have changed most

**ML Models Used**:

- **Statistical Drift Tests**: Kolmogorov-Smirnov test, Population Stability Index (PSI)
- **Distribution Divergence Metrics**: KL divergence, Jensen-Shannon divergence

**UI Requirements** (`/labs/research/ml/monitoring`):

**Primary View: Rolling Accuracy Chart**

- Line chart showing model accuracy over time
- X-axis: Date (last 6 months)
- Y-axis: Accuracy percentage (0-100%)
- Multiple lines: One per model (Logistic, RF, XGBoost, LightGBM)
- Shaded region showing acceptable accuracy range (e.g., 60-75%)
- Red zones where accuracy dropped below threshold
- Annotations marking model retraining dates

**Secondary View: Feature Drift Heatmap**

- Heatmap where:
  - Rows = Features
  - Columns = Time periods (weekly buckets)
  - Cell color = Drift score (white = no drift, yellow = moderate, red = severe)
- Hover tooltip: "RSI_14 drift in week of Dec 15: PSI = 0.42 (moderate drift)"
- Click cell to see distribution comparison plot (historical vs current)

**Tertiary View: Alert Log Table**

- Chronological table of drift alerts
- Columns:
  - Timestamp
  - Alert Type ("Performance Decay", "Feature Drift", "Concept Drift")
  - Severity (Critical, Warning, Info)
  - Description (e.g., "XGBoost accuracy dropped to 58%")
  - Action Taken (e.g., "Model retrained on 12/20")
- Color coded by severity
- Export log button

**Quaternary View: Distribution Comparison Plots**

- Select a feature from dropdown
- Side-by-side histograms:
  - Left: Training data distribution
  - Right: Current data distribution
- Overlay: both distributions on same plot with different colors
- Statistics box: Mean shift, std shift, KS statistic

**Key Interactions**:

- Set custom alert thresholds (e.g., "Alert me if accuracy < 60%")
- "Retrain Model" button (triggers retraining job)
- Subscribe to alerts (email/SMS when critical drift detected)
- Compare any two time periods' distributions

---

### MODULE 8: Error & Failure Regime Analyzer

**Purpose**: When models make mistakes, understand why. Cluster failed predictions to identify risky market conditions where models shouldn't be trusted.

**Business Logic**:

- Collect all misclassified signals (false positives and false negatives)
- Extract market context features when errors occurred
- Cluster errors to find common patterns
- Identify high-risk conditions: "Model fails in X% of cases when volatility spikes + breadth is negative"

**Input Data Requirements**:

- **Misclassified Signals**: Signals where prediction was wrong
- **Market Context Features**: Volatility, regime, breadth, sector rotation at time of error
- **Error Type**: False positive (predicted success, actually failed) vs false negative

**Output Data**:

- **Error Clusters**: Groups of similar failures (e.g., "Failed in volatile sideways markets")
- **High-Risk Conditions**: Specific market contexts with elevated error rates
- **Risk Flags**: Real-time warnings when current conditions match historical failure patterns

**ML Models Used**:

- **K-Means Clustering**: Group errors by feature similarity
- **DBSCAN**: Find dense regions of errors in feature space

**UI Requirements** (`/labs/research/ml/errors`):

**Primary View: Error Heatmap**

- 2D heatmap showing error rate by condition
- Rows: Volatility level (Low, Medium, High, Extreme)
- Columns: Market regime (Bull, Bear, Neutral, Choppy)
- Cell color: Error rate percentage (green = low, red = high)
- Cell annotation: "Error rate: 32% (15/47 signals)"
- Click cell to see list of specific failed signals in that condition

**Secondary View: Failure Cluster Table**

- Table showing discovered error clusters
- Columns:
  - Cluster ID
  - Cluster Description (auto-generated, e.g., "High vol + negative breadth")
  - Error Rate in Cluster (e.g., "45%")
  - Sample Size (number of signals)
  - Common Features (top 3 features defining cluster)
- Sortable by error rate
- Click row to expand and see all signals in that cluster

**Tertiary View: Risk Flag Dashboard**

- Real-time panel showing current market conditions
- Risk meter: "Current conditions match historical failure cluster #3"
- Warning badge if in high-risk regime: ⚠️ "Model unreliable in current conditions"
- List of active risk flags:
  - "Elevated volatility + weak breadth: 38% error rate historically"
  - "Post-earnings window: 29% error rate"
- Recommended action: "Use lower position sizes" or "Wait for regime change"

**Quaternary View: Error Distribution Plots**

- Scatter plot in 2D (using dimensionality reduction)
- X and Y axes: First two principal components of feature space
- Each dot: One signal
- Color: Green (correct prediction) vs Red (error)
- Shows where in feature space errors cluster
- Zoom and pan enabled
- Hover tooltip shows signal details

**Key Interactions**:

- Filter errors: "Show only false positives" or "Show only false negatives"
- Set custom risk thresholds (e.g., "Flag conditions with >30% error rate")
- "Blacklist Condition" button: Exclude signals in this condition from portfolio
- Export error analysis report

---

## LEVEL 4 — STRUCTURE DISCOVERY

**Philosophy**: Markets have hidden structure that can be discovered without supervision—regimes, asset relationships, strategy correlations. These insights inform risk management and diversification.

---

### MODULE 9: Market Regime Discovery Engine

**Purpose**: Automatically discover distinct market regimes from data without predefined labels—find natural clusters in market behavior.

**Business Logic**:

- Collect regime-defining features: returns, volatility, correlations, breadth
- Apply unsupervised clustering to find natural groupings
- Label clusters based on characteristics (e.g., "High vol bear" or "Low vol bull")
- Track regime transitions: probability of moving from one regime to another
- Identify current regime in real-time

**Input Data Requirements**:

- **Market Returns**: Daily returns for major indices (SPY, QQQ, IWM)
- **Volatility Metrics**: VIX, realized volatility, ATR
- **Breadth Indicators**: Advance/decline, new highs/lows, percentage above 200 MA
- **Correlations**: Average pairwise correlation of S&P 500 stocks

**Output Data**:

- **Regime Labels**: Each day assigned to a regime (e.g., Regime 1, 2, 3, 4)
- **Regime Characteristics**: Statistical profile of each regime (avg return, volatility)
- **Transition Probabilities**: Likelihood of moving from regime A to regime B
- **Current Regime**: Real-time identification of today's regime

**ML Models Used**:

1. **K-Means Clustering**: Find 4-6 regime clusters
2. **Hierarchical Clustering**: Alternative method, creates dendrogram

**Clustering Strategy**:

- Use rolling 20-day windows for regime features
- Standardize all features before clustering
- Determine optimal number of clusters via elbow method or silhouette score
- Validate regimes: Do they have distinct performance characteristics?

**UI Requirements** (`/labs/research/regimes`):

**Primary View: Regime Timeline**

- Timeline chart showing regime history
- X-axis: Date (last 5 years)
- Y-axis: Regime label (stacked band chart)
- Each regime colored differently (e.g., Regime 1 = blue, Regime 2 = green, etc.)
- Shows regime duration and transitions clearly
- Overlay: Market index price (secondary Y-axis) to see regime vs price movement
- Hover tooltip: "Regime 3 from Jan 15 - Feb 2: Avg return +0.8%, Vol 18%"

**Secondary View: Regime Characteristics Table**

- Table with one row per discovered regime
- Columns:
  - Regime ID
  - Name (auto-assigned, e.g., "Bull Low Vol")
  - Frequency (% of days in this regime)
  - Avg Daily Return
  - Avg Volatility
  - Avg VIX Level
  - Avg Correlation
  - Best Performing Signals in this regime
- Color coded: Green rows for bull regimes, red for bear
- Click row to drill into regime details

**Tertiary View: Regime Transition Matrix**

- Heatmap showing probability of transitioning between regimes
- Rows: Current regime
- Columns: Next regime
- Cell color: Transition probability (darker = more likely)
- Cell annotation: Percentage (e.g., "35%")
- Diagonal cells (staying in same regime) typically highest probability
- Hover tooltip: "From Regime 2 to Regime 4: 12% probability, avg 8 days before transition"

**Quaternary View: Current Regime Dashboard**

- Large prominent display of current regime
- Regime badge: "Current Regime: Bull Low Vol (Regime 1)"
- Confidence meter: "85% confident in regime classification"
- Time in regime: "18 days in current regime"
- Expected transition: "Most likely next regime: Neutral (22% probability)"
- Historical performance: "Signals in this regime: 68% win rate, +3.2% avg return"

**Quintenary View: Regime Dendrogram** (advanced)

- Tree diagram from hierarchical clustering
- Shows how regimes relate to each other
- Useful for understanding regime similarities
- Interactive: Click branches to collapse/expand

**Key Interactions**:

- Adjust number of regimes (slider 3-10)
- Re-run clustering with different features
- "Name Regimes" tool: Manually assign descriptive names
- Export regime labels for use in other modules
- Filter signals by regime: "Show me all signals that occurred in Regime 3"

---

### MODULE 10: Asset Similarity & Redundancy Map

**Purpose**: Group assets by actual behavior (price co-movement) rather than arbitrary sector classifications. Identify redundant holdings for diversification.

**Business Logic**:

- Calculate correlation matrix of all assets in universe
- Apply clustering to find assets that move together
- Identify redundant pairs: High correlation means low diversification benefit
- Create portfolio redundancy score

**Input Data Requirements**:

- **Asset Returns**: Daily returns for all assets in portfolio or watchlist
- **Correlation Window**: Rolling 60-day or 252-day correlation matrix

**Output Data**:

- **Asset Clusters**: Groups of assets with similar behavior
- **Redundancy Score**: 0-100 metric per asset pair (100 = perfect redundancy)
- **Diversification Report**: Which assets add true diversification vs redundant ones

**ML Models Used**:

1. **Hierarchical Clustering**: Creates dendrogram showing asset relationships
2. **DBSCAN**: Finds dense clusters, labels noise (uncorrelated assets)

**UI Requirements** (`/portfolio/diversification`):

**Primary View: Asset Dendrogram**

- Tree diagram showing hierarchical clustering of assets
- Branches connect similar assets
- Leaf nodes: Individual assets (labeled with ticker)
- Branch height: Correlation distance (shorter = more similar)
- Color coded by discovered clusters
- Hover tooltip: "AAPL and MSFT: 0.82 correlation"
- Interactive: Click branches to collapse/expand, zoom

**Secondary View: Correlation Network Graph**

- Network visualization where:
  - Nodes = Assets (sized by market cap or portfolio weight)
  - Edges = Correlations (only show
    correlations > 0.6)
  - Edge thickness = Correlation strength
  - Node position = Force-directed layout (similar assets cluster together)
- Color coded by cluster
- Hover over node: Shows connected assets and correlation values
- Click node: Highlights all connections
- Zoom and pan enabled

**Tertiary View: Similarity Matrix Heatmap**

- Classic correlation matrix visualization
- Rows and columns: All assets
- Cell color: Correlation value (-1 to +1, red to blue gradient)
- Reordered by clustering: Similar assets grouped together
- Diagonal = 1 (self-correlation)
- Interactive hover: "TSLA vs NVDA: 0.67 correlation"

**Quaternary View: Redundancy Report Table**

- Table listing all asset pairs with high correlation (>0.7)
- Columns:
  - Asset 1
  - Asset 2
  - Correlation
  - Redundancy Score (0-100)
  - Cluster (e.g., "Tech Growth")
  - Portfolio Weight Total (if both held)
  - Recommendation ("Consider reducing exposure")
- Sortable by redundancy score (highest first)
- Color coded: Red for high redundancy (>0.8), yellow for moderate (0.6-0.8)

**Quintenary View: Portfolio Diversification Scorecard**

- Overall portfolio diversification score: 0-100 (100 = perfectly diversified)
- Breakdown by cluster: "35% of portfolio in Tech Growth cluster"
- Concentration risk warning: "Top 3 clusters represent 70% of portfolio"
- Suggested improvements: "Add assets from Defensive or Commodity clusters"
- Visualization: Donut chart showing portfolio weight by cluster

**Key Interactions**:

- Select portfolio mode: Analyze current portfolio vs full watchlist
- Adjust correlation threshold for redundancy (slider 0.5-0.9)
- "Find diversifiers" tool: Given asset X, find least correlated assets
- "Stress test": See how clusters behaved during 2008, 2020, etc.
- Export cluster assignments and correlation matrix

---

### MODULE 11: Strategy Overlap & Crowding Detector

**Purpose**: If running multiple trading strategies, detect when they're redundant (correlated returns) to avoid concentration risk.

**Business Logic**:

- Collect equity curves from each strategy
- Calculate correlation matrix of strategy returns
- Cluster strategies by behavior
- Identify overlapping strategies that don't add diversification

**Input Data Requirements**:

- **Strategy Equity Curves**: Daily PnL or return series for each strategy
- **Strategy Metadata**: Strategy name, type, assets traded

**Output Data**:

- **Strategy Clusters**: Groups of strategies with correlated returns
- **Overlap Warnings**: Pairs of strategies with >0.7 correlation
- **Diversification Score**: 0-100 metric for overall strategy portfolio

**ML Models Used**:

- **Hierarchical Clustering**: Group strategies by return correlation
- **K-Means**: Alternative clustering method

**UI Requirements** (`/labs/research/strategies`):

**Primary View: Strategy Similarity Heatmap**

- Correlation matrix of strategies
- Rows and columns: Strategy names
- Cell color: Return correlation (-1 to +1)
- Reordered by clustering
- Hover tooltip: "Strategy A vs Strategy B: 0.78 correlation (High overlap)"

**Secondary View: Strategy Dendrogram**

- Tree diagram showing strategy relationships
- Leaf nodes: Individual strategies
- Branch height: Correlation distance
- Color coded by cluster
- Identifies strategy "families"

**Tertiary View: Overlap Warning Table**

- Lists all strategy pairs with high correlation (>0.7)
- Columns:
  - Strategy 1
  - Strategy 2
  - Return Correlation
  - Overlap Score (0-100)
  - Combined Capital Allocation (if both running)
  - Risk Assessment ("High redundancy")
- Sortable by overlap score
- Recommendations: "Consider pausing Strategy B or reducing size"

**Quaternary View: Strategy Diversification Scorecard**

- Overall diversification score: 0-100
- Breakdown: "3 clusters identified, 60% of capital in Cluster 1"
- Risk concentration warning: "Top 2 strategies represent 45% of capital"
- Suggested allocation: "Reduce Strategy A by 10%, increase Strategy C by 15%"
- Visualization: Stacked bar chart showing capital by cluster

**Key Interactions**:

- Filter by strategy type: "Show only equity strategies"
- Adjust correlation threshold for overlap warnings
- "Optimize Allocation" tool: Suggests capital allocation for maximum diversification
- Historical view: "How did strategy overlap change over time?"
- Export strategy clusters and recommendations

---

## LEVEL 5 — HUMAN UNDERSTANDABILITY

**Philosophy**: High-dimensional ML feature spaces are impossible to visualize. Dimensionality reduction projects them into 2D/3D for human intuition and pattern recognition.

---

### MODULE 12: Feature Space Embedding Explorer

**Purpose**: Project high-dimensional signal feature space into 2D or 3D for visual exploration. See if similar signals cluster together, outliers, dense regions.

**Business Logic**:

- Take full feature matrix (potentially 50+ features)
- Apply UMAP or t-SNE to reduce to 2 or 3 dimensions
- Preserve local structure: Similar signals stay close in 2D/3D space
- Color points by outcome, regime, or strategy for pattern discovery

**Input Data Requirements**:

- **Feature Matrix**: All engineered features for all historical signals
- **Labels**: Outcomes (success/failure) or regime labels for coloring

**Output Data**:

- **2D or 3D Embeddings**: Coordinates for each signal in reduced space
- **Cluster Assignments**: Optional clustering in reduced space

**ML Models Used**:

1. **UMAP** (Uniform Manifold Approximation and Projection): Fast, preserves global structure
2. **t-SNE** (t-Distributed Stochastic Neighbor Embedding): Classic method, good for local structure

**UI Requirements** (`/labs/research/ml/embedding`):

**Primary View: Interactive 2D Scatter Plot**

- Large interactive scatter plot
- X and Y axes: UMAP dimension 1 and 2 (arbitrary units)
- Each point: One historical signal
- Point color: User-selectable
  - By outcome: Green (success) vs red (failure)
  - By regime: Different color per regime
  - By strategy: Different color per strategy
  - By return magnitude: Gradient from red (loss) to green (gain)
- Point size: Optional encoding (e.g., by volatility)
- Hover tooltip: Shows signal details (asset, date, outcome, features)
- Zoom and pan: Mouse wheel and drag
- Select region: Lasso tool to select points and see details

**Secondary View: 3D Visualization** (optional advanced feature)

- 3D scatter plot using WebGL (Three.js)
- X, Y, Z axes: UMAP dimensions 1, 2, 3
- Same coloring options as 2D
- Rotate view: Click and drag
- Zoom: Scroll
- Hover tooltip: Same signal details
- More immersive for pattern discovery

**Tertiary View: Density Contour Overlay**

- On top of 2D scatter plot, overlay density contours
- Shows where signals cluster densely
- Identifies "hot spots" in feature space
- Useful for finding common signal configurations

**Quaternary View: Cluster Overlay Mode**

- Run K-Means or DBSCAN on 2D embeddings
- Color points by discovered cluster (not by outcome)
- Shows natural groupings in signal space
- Cluster statistics panel: Per-cluster win rate, average return

**Control Panel** (sidebar):

- Dimensionality reduction method: Toggle UMAP vs t-SNE
- Coloring scheme: Dropdown (outcome, regime, strategy, return magnitude)
- Filter controls: Date range, strategy, regime
- "Recompute Embedding" button (if filtering changes)
- Export: Save embedding coordinates, save visualization as image

**Key Interactions**:

- Click any point: Opens signal detail modal with full features and outcome
- Lasso select multiple points: Bulk analyze (e.g., "What's the win rate in this region?")
- Compare regions: Select region A and region B, show statistical comparison
- "Find Similar Signals" tool: Click a point, highlights k-nearest neighbors
- Animate over time: Time slider showing how new signals appear in space (advanced)

---

### MODULE 13: Regime Separation Quality Analyzer

**Purpose**: Validate that market regimes discovered in Module 9 are truly distinct. In feature space, do different regimes occupy separate regions (good separation) or overlap (poor separation)?

**Business Logic**:

- Use embeddings from Module 12
- Color points by regime label
- Calculate separation metrics: Are regime clusters tight and far apart?
- Identify overlapping regimes that may need merging

**Input Data Requirements**:

- **2D/3D Embeddings**: From Module 12
- **Regime Labels**: From Module 9

**Output Data**:

- **Separation Score**: 0-100 metric (100 = perfect separation)
- **Overlap Matrix**: For each regime pair, degree of overlap
- **Regime Tightness**: How compact each regime cluster is

**ML Models Used**:

- **Distance Metrics**: Euclidean distance between regime centroids
- **Silhouette Score**: Clustering quality metric
- **Calinski-Harabasz Index**: Another clustering validation metric

**UI Requirements** (`/labs/research/ml/embedding`):

**Primary View: Regime-Colored Embedding Plot**

- 2D scatter plot (same as Module 12)
- Points colored by regime label (e.g., Regime 1 = blue, Regime 2 = green, etc.)
- Regime centroids marked with large symbols (X or star)
- Visually assess separation: Good separation = distinct color clusters, poor separation = colors mixed

**Secondary View: Regime Overlap Matrix**

- Heatmap where:
  - Rows and columns: Regimes
  - Cell color: Overlap score (white = no overlap, red = high overlap)
  - Cell annotation: Percentage (e.g., "15% overlap")
- Diagonal cells: Regime tightness score (how compact the regime is)
- Hover tooltip: "Regime 1 and Regime 3 overlap in 15% of observations"

**Tertiary View: Separation Metrics Table**

- Table with one row per regime pair
- Columns:
  - Regime A
  - Regime B
  - Distance Between Centroids
  - Overlap Score (0-100)
  - Recommendation ("Well separated", "Consider merging", "Ambiguous boundary")
- Sortable by overlap score (highest overlap = most problematic)
- Color coded: Green (good separation), yellow (moderate), red (poor separation)

**Quaternary View: Overall Regime Quality Scorecard**

- Summary metrics:
  - Overall separation score: 0-100
  - Silhouette score
  - Number of ambiguous observations (points near regime boundaries)
- Recommendations:
  - "Regime 2 and Regime 4 are highly overlapping. Consider merging."
  - "Regime 3 is very tight and well-separated. Good regime definition."
- Visualization: Radar chart showing per-regime tightness and separation

**Key Interactions**:

- Click overlap matrix cell: Highlights those two regimes in embedding plot
- Filter: "Show only ambiguous observations" (points near boundaries)
- "Merge Regimes" tool: Select regimes to merge, recomputes analysis
- Compare embedding methods: "Does t-SNE show better separation than UMAP?"
- Export validation report with recommendations

---

## LEVEL 6 — EXECUTIVE & DECISION SUPPORT

**Philosophy**: All the ML in the world is useless if executives and portfolio managers can't quickly make decisions. This level aggregates insights into actionable scorecards and advisories.

---

### MODULE 14: Signal Quality Scorecard

**Purpose**: Aggregate all information about a signal—returns, risk, ML confidence, regime suitability—into a single composite quality score. Rank signals for portfolio construction.

**Business Logic**:

- Collect multiple metrics per signal:
  - Historical return
  - Win rate
  - Sharpe ratio
  - Maximum drawdown
  - ML success probability
  - Confidence tier
  - Regime fit score
- Weight and combine into composite score (0-100)
- Rank all signals by quality score

**Input Data Requirements**:

- **Historical Performance**: Returns, win rate, Sharpe, drawdown per signal
- **ML Predictions**: Success probability from Module 3, consensus score from Module 5
- **Regime Context**: Does current regime match signal's best regime?
- **Risk Metrics**: Volatility, correlation to portfolio

**Output Data**:

- **Composite Quality Score**: 0-100 (100 = highest quality)
- **Score Breakdown**: Contribution from each component (return, ML confidence, etc.)
- **Ranked Leaderboard**: Signals sorted by quality

**ML Models Used**:

- **Weighted Aggregation**: Linear combination of normalized metrics
- **Principal Component Analysis** (optional): Reduce metrics to composite score

**Weighting Scheme** (customizable):

- Historical Return: 25%
- Sharpe Ratio: 20%
- ML Success Probability: 25%
- Win Rate: 15%
- Regime Fit: 10%
- Model Confidence: 5%

**UI Requirements** (`/portfolio/signals`):

**Primary View: Signal Scorecard Table**

- Sortable table of all active signals
- Columns:
  - Signal Name
  - Asset
  - **Quality Score** (large, color-coded: >80 dark green, 60-80 light green, 40-60 yellow, <40 red)
  - Historical Return
  - Sharpe Ratio
  - Win Rate
  - ML Probability
  - Regime Fit (badge: "Optimal", "Good", "Poor")
  - Action (button: "Add to Portfolio", "Set Alert")
- Default sort: Quality score descending
- Filters: Minimum quality score, specific strategies, specific assets
- Top 10 signals highlighted in special color

**Expanded Detail Card** (click row):

- Large quality score gauge (circular, 0-100)
- Score breakdown: Horizontal stacked bar showing contribution from each component
  - Return component (green segment): 20 points
  - Sharpe component (blue segment): 18 points
  - ML component (purple segment): 22 points
  - Win rate component (yellow segment): 12 points
  - Regime fit component (orange segment): 8 points
- Radar chart: 6 axes (Return, Sharpe, ML Prob, Win Rate, Regime Fit, Confidence), polygon showing signal's profile
- Comparison: "Top quartile in ML probability, bottom quartile in win rate"
- Historical quality score trend: Line chart showing quality score over last 30 days
- Action buttons: "Include in next rebalance", "Set threshold alert"

**Secondary View: Quality Score Distribution**

- Histogram showing distribution of quality scores across all signals
- X-axis: Quality score bins (0-10, 10-20, ..., 90-100)
- Y-axis: Number of signals
- Color gradient: Red to green
- Median line: Shows median quality score
- Helps identify if current market has many high-quality opportunities

**Tertiary View: Leaderboard (Top 20)**

- Podium-style display showing top 20 signals
- Large cards with:
  - Rank number
  - Signal name
  - Asset
  - Quality score (large font)
  - Mini sparkline showing recent performance
- Click card for full detail
- "Export Top 20" button for further analysis

**Quaternary View: Custom Scorecard Builder** (advanced)

- Adjust component weights: Sliders for each metric
  - Return weight (0-100%)
  - Sharpe weight (0-100%)
  - ML probability weight (0-100%)
  - Win rate weight (0-100%)
  - Regime fit weight (0-100%)
  - Model confidence weight (0-100%)
- Weights must sum to 100% (auto-normalize)
- "Recalculate Scores" button
- Save custom scorecard: Name and save configuration for future use
- Useful for different investment philosophies (e.g., risk-focused vs return-focused)

**Key Interactions**:

- Sort by any column in scorecard table
- Filter: "Show only high-quality signals" (score > 70)
- Bulk actions: Select multiple signals, "Add all to watch list"
- Compare two signals side-by-side: Select two, see radar chart overlay
- Historical view: "How did quality scores look 1 month ago?"
- Export scorecard as CSV or PDF report

---

### MODULE 15: ML-Driven Position Sizing Advisor

**Purpose**: Given ML confidence and portfolio risk constraints, recommend optimal position sizes. Higher confidence = larger size, but respect risk limits.

**Business Logic**:

- Input: Signal ML probability, asset volatility, current portfolio composition
- Calculate risk contribution: How much risk would this position add?
- Suggest position size bands: Conservative, moderate, aggressive
- Consider portfolio correlation: Don't oversize correlated positions
- Apply Kelly Criterion or similar sizing framework

**Input Data Requirements**:

- **Signal Confidence**: ML success probability from Module 3
- **Asset Volatility**: Historical volatility (ATR, standard deviation)
- **Current Portfolio**: Existing positions, total capital, risk tolerance
- **Correlation Matrix**: How does this asset correlate with portfolio?

**Output Data**:

- **Recommended Position Size**: In dollars, shares, or % of portfolio
- **Size Bands**: Conservative (1%), Moderate (3%), Aggressive (5%)
- **Risk Contribution Estimate**: How much portfolio variance increases
- **Stress Scenarios**: Position size under different market conditions

**ML Models Used**:

- **Linear Regression**: Predict position size from confidence + risk features
- **Rule-Based System**: Kelly Criterion, risk parity adjustments

**Sizing Framework**:

- Base size = f(ML probability): Higher probability → larger base size
- Volatility adjustment: Higher volatility → reduce size
- Correlation adjustment: High correlation to portfolio → reduce size
- Risk budget: Don't exceed max risk per position (e.g., 2% portfolio volatility)

**UI Requirements** (`/portfolio/risk`):

**Primary View: Position Sizing Recommendation Panel**

- Signal selector dropdown: Choose which signal to size
- Large recommended size display: "Recommended: 150 shares ($22,500)"
- Size tier badges:
  - Conservative: 100 shares ($15,000) — "Low risk, high confidence required"
  - Moderate: 150 shares ($22,500) — "Balanced risk-reward"
  - Aggressive: 200 shares ($30,000) — "Higher risk, strong conviction"
- Current ML confidence: "78% success probability"
- Asset volatility: "15% annualized volatility (Moderate)"
- Rationale: "Higher than average confidence in bullish regime; moderate volatility justifies 3% allocation"

**Secondary View: Risk vs Size Curve**

- Line chart showing relationship between position size and portfolio risk
- X-axis: Position size (% of portfolio or $ amount)
- Y-axis: Incremental portfolio variance or VaR
- Curve shows accelerating risk as size increases
- Markers for Conservative, Moderate, Aggressive sizes
- Red zone: Sizes that exceed risk budget
- Hover tooltip: "At $30,000 position, portfolio VaR increases by 1.2%"

**Tertiary View: Allocation Table**

- Table showing all active signals with recommended sizes
- Columns:
  - Signal Name
  - Asset
  - ML Confidence
  - Volatility
  - Recommended Size (Moderate tier)
  - Risk Contribution (% of portfolio variance)
  - Correlation to Portfolio
  - Action (button: "Apply", "Adjust", "Skip")
- Sortable by risk contribution or size
- Summary row: Total capital allocated, total risk added

**Quaternary View: Stress Scenario Analysis**

- "What if" scenarios showing position performance under stress
- Scenarios:
  - Market crash (-20%): "Position would lose $X"
  - Volatility spike (VIX → 40): "Position would become $X more volatile"
  - Correlation breakdown: "If correlations rise to 0.9, portfolio risk increases by X%"
- Table showing position size recommendations under each scenario
- Helps decide if current size is robust to stress

**Quintenary View: Portfolio Composition Pie Chart**

- After applying recommendations, show updated portfolio
- Pie chart: Each slice = one position, sized by $ allocation
- Color coded by sector or strategy
- Highlight new positions in bright color
- Stats: Total capital used, % of portfolio in signals, remaining cash

**Control Panel** (sidebar):

- Risk tolerance slider: Conservative / Moderate / Aggressive (affects all recommendations)
- Max position size limit: "$50,000 per position" or "5% of portfolio per position"
- Correlation threshold: "Don't exceed 0.7 avg correlation with portfolio"
- Kelly fraction: "Use 50% Kelly" (adjusts sizing aggressiveness)
- "Recalculate All Sizes" button

**Key Interactions**:

- Adjust size manually: Override recommendation with custom size
- "Optimize Portfolio" button: Runs optimization to find best allocation across all signals
- Lock positions: Exclude certain positions from rebalancing
- Save allocation: "Save current allocation as portfolio snapshot"
- Export sizing recommendations as CSV
- Set alerts: "Notify me when recommended size changes by >20%"

---

## TECHNICAL IMPLEMENTATION NOTES

### Data Pipeline Architecture

**Data Flow**:

1. **Raw Data Ingestion** → OHLCV, indicators, breadth metrics from market data API
2. **Feature Engineering** → Module 2 processes raw data into ML-ready features
3. **Dataset Construction** → Module 1 creates labeled training data
4. **Model Training** → Modules 3, 5, 9, 10, 11 train their respective models
5. **Inference** → Real-time predictions for active signals
6. **Monitoring** → Module 7 tracks performance and drift
7. **Explainability** → Module 6 generates SHAP values post-prediction
8. **Aggregation** → Modules 14, 15 combine insights for decision support

**Storage Requirements**:

- **Time-Series Database**: For OHLCV, indicators (TimescaleDB or InfluxDB)
- **Feature Store**: Versioned feature sets (Feast or custom solution)
- **Model Registry**: Trained models with metadata (MLflow or custom)
- **Results Database**: Predictions, outcomes, evaluations (PostgreSQL)
- **Artifact Storage**: Charts, reports, embeddings (S3 or local filesystem)

### Model Training Schedule

- **Daily**: Retrain Module 3 (Signal Success Probability) with last night's outcomes
- **Weekly**: Retrain Module 9 (Regime Discovery) as regimes change slowly
- **Monthly**: Retrain Modules 10, 11 (Asset Clustering, Strategy Overlap)
- **On-Demand**: Modules 12, 13 (Embeddings) recalculated when requested
- **Continuous**: Module 7 (Drift Monitoring) runs every hour

### Model Persistence

Each model stores:

- Trained model object (pickled scikit-learn, XGBoost, etc.)
- Hyperparameters and config
- Training date and dataset version
- Validation metrics (accuracy, precision, recall, F1, AUC-ROC)
- SHAP explainer object (for Module 6)

### API Design

**Backend Endpoints**:

- `POST /api/ml/train/{module_id}` — Trigger model training
- `GET /api/ml/predict/{module_id}` — Get predictions for current signals
- `GET /api/ml/explain/{signal_id}` — Get SHAP values for specific signal
- `GET /api/ml/monitor/drift` — Get drift metrics
- `GET /api/ml/regimes/current` — Get current market regime
- `GET /api/ml/clusters/{type}` — Get asset or strategy clusters
- `POST /api/ml/embedding/compute` — Generate embeddings
- `GET /api/portfolio/scorecard` — Get signal quality scores
- `GET /api/portfolio/sizing/{signal_id}` — Get position size recommendation

### Performance Optimization

**Caching Strategy**:

- Cache SHAP values: Expensive to compute, cache for 1 hour
- Cache embeddings: Recompute only when new data added
- Cache regime classifications: Update daily
- Cache feature engineering: Store processed features, reuse across models

**Lazy Loading**:

- Load full historical data only on demand
- Default views show last 6 months, "Load More" for full history
- Progressive rendering: Show partial results while computing

**Background Jobs**:

- Model training runs in background (Celery or similar)
- Long computations (embeddings, clustering) run async
- User gets notification when complete

### Error Handling & Validation

**Data Validation**:

- Check for missing values, outliers before training
- Validate feature distributions match expected ranges
- Alert if input data looks anomalous

**Model Validation**:

- All models validated on hold-out test set before deployment
- Minimum accuracy threshold: 55% (better than random)
- Models failing validation are not deployed, alert sent to admin

**Graceful Degradation**:

- If ML model fails, fall back to simple heuristics
- Show warning: "ML predictions unavailable, using historical averages"
- System remains functional without ML

### Security & Access Control

**User Roles**:

- **Viewer**: Can view dashboards, read-only
- **Analyst**: Can view, adjust parameters, re-run analyses
- **Admin**: Can train models, modify configurations, access backend

**Data Privacy**:

- No PII or sensitive data in ML models
- User-specific portfolios isolated (no cross-user data leakage)
- Audit logs for all model training and predictions

### Testing Strategy

**Unit Tests**:

- Test each feature engineering function
- Test model training pipeline (on synthetic data)
- Test prediction functions

**Integration Tests**:

- End-to-end: Raw data → features → training → prediction → UI
- Test all API endpoints

**ML-Specific Tests**:

- Test for data leakage (future data not in training)
- Test model serialization/deserialization
- Test SHAP explainer consistency

**Performance Tests**:

- Load test: 10,000 signals, prediction latency <100ms
- Stress test: Train models on 5 years of data, complete <10 min

---

## UI/UX DESIGN PRINCIPLES

### Visual Design Standards

**Color Palette**:

- Background: Dark navy (#0a0e27) or dark gray (#1a1a2e)
- Primary accent: Electric blue (#00d4ff) for interactive elements
- Success: Bright green (#00ff88) for positive metrics
- Warning: Amber (#ffaa00) for moderate alerts
- Danger: Bright red (#ff4444) for critical alerts
- Neutral: Light gray (#a0a0a0) for secondary text

**Typography**:

- Headers: Inter or Roboto, bold, 18-24px
- Body: Inter or Roboto, regular, 14-16px
- Data values: Roboto Mono or Source Code Pro, 12-14px (monospace for alignment)
- Large numbers: 32-48px for key metrics (quality scores, probabilities)

**Chart Design**:

- Use Recharts or Chart.js for consistency
- Dark backgrounds with bright data lines/bars
- Subtle grid lines (10% opacity)
- Large, clear axis labels
- Tooltips on hover with detailed info
- Legend always visible, clickable to toggle series

**Table Design**:

- Alternating row colors for readability (subtle, 5% opacity difference)
- Sticky headers when scrolling
- Sortable columns with arrow indicators
- Hover highlighting entire row
- Color-coded cells where appropriate (heatmap style)
- Pagination or virtual scrolling for >100 rows

**Interactive Elements**:

- Buttons: Rounded corners, subtle shadow, hover state (slight lift)
- Inputs: Outlined style, focus state (blue glow)
- Dropdowns: Searchable for long lists
- Sliders: Clear value display, snap to increments
- Tooltips: Appear on hover, dismiss on mouse out, max width 300px

### Loading States

**Never show blank screens**:

- Skeleton loaders: Gray animated placeholders for tables, charts
- Loading spinners: For async operations (training, fetching)
- Progress bars: For long operations (model training, embedding computation)
- Optimistic updates: Show prediction immediately, mark "pending" until confirmed

**Progressive Loading**:

- Show most important data first (e.g., top 10 signals, then load rest)
- "Loading..." indicator for secondary data
- "Load More" button for historical data

### Responsive Design

**Desktop-First** (traders use large monitors):

- Optimize for 1920x1080 and wider
- Multi-column layouts to maximize screen space
- Side-by-side comparisons common

**Tablet Support** (iPad Pro):

- Collapse sidebars to hamburger menu
- Stack multi-column layouts vertically
- Scrollable tables

**Mobile Not Primary** (but functional):

- Focus on dashboards and scorecards
- Training and detailed analysis on desktop only
- Read-only views on mobile

### Accessibility

**Keyboard Navigation**:

- All interactive elements accessible via Tab
- Shortcuts: Ctrl+F for search, Ctrl+R for refresh, etc.

**Color Blind Safe**:

- Never rely solely on color (use icons, patterns, labels)
- Test with color blindness simulator

**Screen Reader Support**:

- ARIA labels for all charts and tables
- Alt text for images
- Semantic HTML

---

## DEPLOYMENT & OPERATIONS

### Infrastructure

**Frontend**:

- React (TypeScript) with Next.js for SSR
  -ets

**Backend**:

- Python (FastAPI or Flask)
-
- Auto-scaling based on load

**ML Infrastructure**:

-
- CPU instances sufficient for tree-based models
- Model serving via FastAPI endpoints

**Monitoring**:

- Application monitoring: Datadog, New Relic, or Grafana
- ML monitoring: Custom dashboards (Module 7)
- Alerting: PagerDuty or email alerts for critical issues

es

### Monitoring & Alerts

**Application Health**:

- Uptime monitoring: 99.9% SLA
- Response time: 95th percentile <200ms
- Error rate: <0.1%

**ML Health**:

- Model accuracy tracked daily (Module 7)
- Alert if accuracy drops >5% below baseline
- Alert if drift score >70
- Alert if prediction latency >500ms

### Cost Optimization

**Compute**:

- Use spot instances for model training (non-critical)
- **Data Storage**:

- Compress historical data
- Archive old signals (>2 years) to cold storage
- Optimize database indexes

**API Calls**:

- Cache external API responses (market data)
- Batch requests where possible
- Rate limit to avoid overages

---

### ML Performance Metrics

- **Signal Success Prediction Accuracy**: >60% (significantly better than random)
- **Model Agreement**: Consensus disagreement <15% on average (models aligned)
- **Regime Classification Silhouette Score**: >0.5 (well-separated regimes)
- **Drift Detection**: Alert issued >7 days before severe performance decay

### Technical Performance Metrics

- **Uptime**: >99.9%
- **Prediction Latency**: <100ms for

this was the spec
