**1. Probability Theory and Stochastic Calculus**

**1.1 Random Variables and Stochastic Processes**

- Discrete and continuous random variables
- Probability distributions (normal, log-normal, etc.)
- Joint, marginal, and conditional distributions
- Stochastic processes and filtrations
- Stationarity and ergodicity
- Path properties (continuity, Hölder regularity, non-differentiability)

**1.2 Markov Chains**

- Discrete-time Markov chains
- Transition matrices
- Stationary distributions
- Classification of states (transient, recurrent, absorbing)
- Continuous-time Markov chains
- Infinitesimal generators
- Kolmogorov equations

**1.3 Diffusion Processes**

- Brownian motion
- Ito processes
- Stochastic differential equations (SDEs)
- Geometric Brownian motion
- Ornstein-Uhlenbeck process
- Cox-Ingersoll-Ross (CIR) process

**1.4 Martingales**

- Martingale definition and properties
- Submartingales and supermartingales
- Optional stopping theorem
- Martingale representation theorem
- Doob decomposition
- Change of measure (Girsanov’s theorem)

**1.5 Jump Processes**

- Poisson processes
- Compound Poisson processes
- Lévy processes
- Jump-diffusion models (Merton, Kou)
- Variance gamma process

**1.6 Copulas**

- Sklar’s theorem
- Gaussian copula
- t-copula
- Archimedean copulas (Clayton, Gumbel, Frank)
- Tail dependence
- Used mainly for stress testing and scenario analysis post-2008

**1.7 Stochastic Calculus**

- Ito’s lemma
- Ito’s lemma for jump diffusions
- Stochastic integration

**1.8 No-Arbitrage and Market Completeness**

- No-arbitrage principle
- Complete and incomplete markets
- Equivalent martingale measure (EMM)
- Fundamental theorems of asset pricing
- Risk-neutral pricing
- Replicating portfolios

---

**2. Statistics and Time Series Analysis**

**2.1 Statistical Estimation**

- Parametric estimation methods
- Non-parametric methods
- Semi-parametric approaches
- Maximum likelihood estimation (MLE)
- Method of moments
- Expectation-maximization (EM) algorithm
- Bayesian estimation
- Kernel density estimation

**2.2 Regression Analysis**

- Linear regression (OLS)
- Ridge regression (L2 regularization)
- Lasso regression (L1 regularization)
- Elastic Net
- Quantile regression
- Robust regression (M-estimators, Huber loss)
- Generalized linear models (GLM)
- Logistic regression

**2.3 Hypothesis Testing**

- Null and alternative hypotheses
- Type I and Type II errors
- t-tests, F-tests, chi-squared tests
- Likelihood ratio tests
- Wald tests
- Multiple testing corrections (Bonferroni, FDR)
- Backtesting and out-of-sample testing

**2.4 Factor Models and Dimensionality Reduction**

- Single-factor models (CAPM)
- Multi-factor models (Fama-French, Carhart)
- Arbitrage pricing theory (APT)
- Principal component analysis (PCA)
- Factor analysis
- Independent component analysis (ICA)
- Autoencoders
- Hierarchical factor models

**2.5 Time Series Models**

- Autoregressive (AR) models
- Moving average (MA) models
- ARMA models
- ARIMA models
- Seasonal ARIMA (SARIMA)
- Box-Jenkins methodology
- Autocorrelation and partial autocorrelation functions

**2.6 Volatility Modeling**

- ARCH models
- GARCH models
- EGARCH (exponential GARCH)
- GJR-GARCH (threshold GARCH)
- FIGARCH (fractionally integrated GARCH)
- Multivariate GARCH (BEKK, DCC)
- Realized volatility

**2.7 Cointegration and Mean Reversion**

- Unit root tests (ADF, Phillips-Perron)
- Cointegration testing (Engle-Granger, Johansen)
- Error correction models (ECM)
- Vector error correction models (VECM)
- Mean reversion tests
- Half-life estimation

**2.8 Regime-Switching Models**

- Markov-switching models
- Hamilton filter

**2.9 Filtering and State-Space Models**

- Kalman filter
- Extended Kalman filter (EKF)
- Unscented Kalman filter (UKF)
- Particle filters
- State-space models
- Dynamic linear models

---

**3. Machine Learning**

**3.1 Supervised Learning**

- Linear and logistic regression
- Decision trees
- Random forests
- Gradient boosting (XGBoost, LightGBM, CatBoost)
- Support vector machines (SVM)
- k-nearest neighbors (k-NN)
- Naive Bayes

**3.2 Unsupervised Learning**

- k-means clustering
- Hierarchical clustering
- DBSCAN
- Gaussian mixture models (GMM)
- t-SNE and UMAP for visualization
- Anomaly detection

**3.3 Neural Networks and Deep Learning**

- Feedforward neural networks
- Backpropagation
- Activation functions (ReLU, sigmoid, tanh)
- Convolutional neural networks (CNNs)
- Recurrent neural networks (RNNs)
- Long short-term memory (LSTM)
- Gated recurrent units (GRU)
- Attention mechanisms
- Transformers
- Autoencoders and variational autoencoders (VAE)
- Generative adversarial networks (GANs)

**3.4 Model Evaluation and Selection**

- Bias-variance tradeoff
- Cross-validation (k-fold, time series CV)
- Train-validation-test splits
- Walk-forward analysis
- Expanding and rolling windows
- Purging and embargo for time series
- Information coefficient (IC) and IC decay
- Sharpe ratio and other performance metrics

**3.5 Regularization and Overfitting Prevention**

- L1 and L2 regularization
- Dropout
- Early stopping
- Data augmentation
- Batch normalization
- Ensemble methods (bagging, boosting, stacking)

**3.6 Specialized Techniques**

- Gaussian processes
- Bayesian optimization
- Reinforcement learning
- Transfer learning
- Meta-learning
- Natural language processing (NLP)
- Sentiment analysis

**3.7 Financial ML Pitfalls**

- Non-IID data and temporal dependence
- Non-stationarity and regime changes
- PnL-aligned loss functions vs. prediction accuracy
- Transaction costs and market impact
- Data snooping and p-hacking

---

**4. Numerical Methods and Optimization**

**4.4 Ordinary Differential Equations (ODEs)**

- Euler method
- Runge-Kutta methods (RK4)
- Adaptive step-size methods
- Implicit methods for stiff ODEs
- Boundary value problems

**4.5 Partial Differential Equations (PDEs)**

- Finite difference methods (FDM)
- Explicit schemes
- Implicit schemes
- Crank-Nicolson scheme
- Finite element methods (FEM)
- Spectral methods
- Handling cross terms and reactive terms

**4.6 Stochastic Differential Equations (SDEs)**

- Euler-Maruyama method
- Milstein scheme
- Stochastic Runge-Kutta schemes (limited practical use)
- Exact simulation schemes (for select processes: GBM, OU, CIR)

**4.7 Monte Carlo Simulation**

- Standard Monte Carlo

**4.8 Optimization**

- Gradient descent
- Stochastic gradient descent (SGD)
- Newton’s method
- Quasi-Newton methods (BFGS)
- Conjugate gradient
- Levenberg-Marquardt algorithm
- Convex optimization
- Quadratic programming
- Linear programming
- Global optimization (simulated annealing, genetic algorithms)

**4.9 Fast Fourier Transform (FFT)**

- Discrete Fourier transform
- FFT algorithms
- Carr-Madan formula for option pricing
- COS method
- Fourier pricing under Lévy models
- Convolution theorem
