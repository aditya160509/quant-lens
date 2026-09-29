export const STRATEGIES = {
    macd: {
        id: 'macd',
        name: 'MACD Crossover',
        cat: 'momentum',
        desc: 'Classic 12/26/9 signal line crossover. Industry standard for momentum detection.',
        risk: 'Medium',
        code: `# MACD Crossover - Classic 12/26/9
class Strategy:
    def __init__(self):
        self.fast = 12
        self.slow = 26
        self.signal = 9
        
    def generate_signals(self, data):
        close = data['Close']
        ema_fast = close.ewm(span=self.fast).mean()
        ema_slow = close.ewm(span=self.slow).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=self.signal).mean()
        
        signals = []
        for i in range(1, len(close)):
            if macd.iloc[i] > signal.iloc[i] and macd.iloc[i-1] <= signal.iloc[i-1]:
                signals.append({'idx': i, 'dir': 1})
            elif macd.iloc[i] < signal.iloc[i] and macd.iloc[i-1] >= signal.iloc[i-1]:
                signals.append({'idx': i, 'dir': -1})
        return signals

strategy = Strategy()`
    },
    momentum: {
        id: 'momentum',
        name: 'Momentum Alpha',
        cat: 'momentum',
        desc: '20-day price velocity breakout with threshold confirmation.',
        risk: 'High',
        code: `# Momentum 20-Day Breakout
class Strategy:
    def __init__(self):
        self.lookback = 20
        self.threshold = 0.02
        
    def generate_signals(self, data):
        close = data['Close']
        signals = []
        pos = 0
        for i in range(self.lookback, len(close)):
            ret = (close.iloc[i] / close.iloc[i-self.lookback]) - 1
            if ret > self.threshold and pos <= 0:
                signals.append({'idx': i, 'dir': 1})
                pos = 1
            elif ret < -self.threshold and pos >= 0:
                signals.append({'idx': i, 'dir': -1})
                pos = -1
        return signals

strategy = Strategy()`
    },
    rsi: {
        id: 'rsi',
        name: 'RSI Reversal',
        cat: 'reversal',
        desc: 'Oversold (30) / Overbought (70) mean reversion strategy.',
        risk: 'Medium',
        code: `# RSI Oversold/Overbought Reversal
class Strategy:
    def __init__(self):
        self.period = 14
        self.oversold = 30
        self.overbought = 70
        
    def rsi(self, prices):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.period).mean()
        return 100 - (100 / (1 + gain / (loss + 1e-10)))
        
    def generate_signals(self, data):
        rsi_val = self.rsi(data['Close'])
        signals = []
        for i in range(self.period, len(rsi_val)):
            if rsi_val.iloc[i] < self.oversold and rsi_val.iloc[i-1] >= self.oversold:
                signals.append({'idx': i, 'dir': 1})
            elif rsi_val.iloc[i] > self.overbought and rsi_val.iloc[i-1] <= self.overbought:
                signals.append({'idx': i, 'dir': -1})
        return signals

strategy = Strategy()`
    },
    dualma: {
        id: 'dualma',
        name: 'Golden Cross 50/200',
        cat: 'trend',
        desc: 'Institutional trend-following using 50/200 SMA crossover.',
        risk: 'Low',
        code: `# Golden Cross - 50/200 SMA
class Strategy:
    def __init__(self):
        self.fast = 50
        self.slow = 200
        
    def generate_signals(self, data):
        close = data['Close']
        sma_fast = close.rolling(self.fast).mean()
        sma_slow = close.rolling(self.slow).mean()
        
        signals = []
        for i in range(self.slow + 1, len(close)):
            if sma_fast.iloc[i] > sma_slow.iloc[i] and sma_fast.iloc[i-1] <= sma_slow.iloc[i-1]:
                signals.append({'idx': i, 'dir': 1})
            elif sma_fast.iloc[i] < sma_slow.iloc[i] and sma_fast.iloc[i-1] >= sma_slow.iloc[i-1]:
                signals.append({'idx': i, 'dir': -1})
        return signals

strategy = Strategy()`
    },
    bbands: {
        id: 'bbands',
        name: 'Bollinger Bands',
        cat: 'volatility',
        desc: 'Mean reversion using 2-sigma bands around 20-day SMA.',
        risk: 'Medium',
        code: `# Bollinger Bands - 20/2 Standard
class Strategy:
    def __init__(self):
        self.period = 20
        self.std_dev = 2
        
    def generate_signals(self, data):
        close = data['Close']
        sma = close.rolling(self.period).mean()
        std = close.rolling(self.period).std()
        upper = sma + (std * self.std_dev)
        lower = sma - (std * self.std_dev)
        
        signals = []
        pos = 0
        for i in range(self.period, len(close)):
            if close.iloc[i] < lower.iloc[i] and pos <= 0:
                signals.append({'idx': i, 'dir': 1})
                pos = 1
            elif close.iloc[i] > upper.iloc[i] and pos >= 0:
                signals.append({'idx': i, 'dir': -1})
                pos = -1
            elif pos != 0 and lower.iloc[i] < close.iloc[i] < upper.iloc[i]:
                if pos == 1 and close.iloc[i] > sma.iloc[i]:
                    signals.append({'idx': i, 'dir': -1})
                    pos = 0
                elif pos == -1 and close.iloc[i] < sma.iloc[i]:
                    signals.append({'idx': i, 'dir': 1})
                    pos = 0
        return signals

strategy = Strategy()`
    },
    stochastic: {
        id: 'stochastic',
        name: 'Stochastic Oscillator',
        cat: 'reversal',
        desc: '%K/%D crossover at extreme levels (20/80).',
        risk: 'Medium',
        code: `# Stochastic Oscillator - 14/3/3
class Strategy:
    def __init__(self):
        self.k_period = 14
        self.d_period = 3
        self.oversold = 20
        self.overbought = 80
        
    def generate_signals(self, data):
        high = data['High']
        low = data['Low']
        close = data['Close']
        
        lowest_low = low.rolling(self.k_period).min()
        highest_high = high.rolling(self.k_period).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
        d = k.rolling(self.d_period).mean()
        
        signals = []
        for i in range(self.k_period + self.d_period, len(close)):
            if k.iloc[i] > d.iloc[i] and k.iloc[i-1] <= d.iloc[i-1] and k.iloc[i] < self.oversold:
                signals.append({'idx': i, 'dir': 1})
            elif k.iloc[i] < d.iloc[i] and k.iloc[i-1] >= d.iloc[i-1] and k.iloc[i] > self.overbought:
                signals.append({'idx': i, 'dir': -1})
        return signals

strategy = Strategy()`
    },
    atr_breakout: {
        id: 'atr_breakout',
        name: 'ATR Volatility Breakout',
        cat: 'volatility',
        desc: 'Breakout above/below ATR bands for trend initiation.',
        risk: 'High',
        code: `# ATR Volatility Breakout
class Strategy:
    def __init__(self):
        self.atr_period = 14
        self.multiplier = 2.0
        
    def generate_signals(self, data):
        high = data['High']
        low = data['Low']
        close = data['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(self.atr_period).mean()
        
        sma = close.rolling(20).mean()
        upper = sma + (atr * self.multiplier)
        lower = sma - (atr * self.multiplier)
        
        signals = []
        pos = 0
        for i in range(20, len(close)):
            if close.iloc[i] > upper.iloc[i] and pos <= 0:
                signals.append({'idx': i, 'dir': 1})
                pos = 1
            elif close.iloc[i] < lower.iloc[i] and pos >= 0:
                signals.append({'idx': i, 'dir': -1})
                pos = -1
        return signals

strategy = Strategy()`
    },
    vwap: {
        id: 'vwap',
        name: 'VWAP Cross',
        cat: 'trend',
        desc: 'Volume-weighted average price crossover for intraday bias.',
        risk: 'Low',
        code: `# VWAP Crossover Strategy
class Strategy:
    def __init__(self):
        self.period = 20
        
    def generate_signals(self, data):
        close = data['Close']
        volume = data['Volume']
        
        vwap = (close * volume).rolling(self.period).sum() / volume.rolling(self.period).sum()
        
        signals = []
        for i in range(self.period + 1, len(close)):
            if close.iloc[i] > vwap.iloc[i] and close.iloc[i-1] <= vwap.iloc[i-1]:
                signals.append({'idx': i, 'dir': 1})
            elif close.iloc[i] < vwap.iloc[i] and close.iloc[i-1] >= vwap.iloc[i-1]:
                signals.append({'idx': i, 'dir': -1})
        return signals

strategy = Strategy()`
    }
};

export const STRATEGY_CATEGORIES = {
    momentum: { name: 'Momentum', icon: 'Zap', desc: 'Trend continuation strategies' },
    trend: { name: 'Trend Following', icon: 'TrendingUp', desc: 'Long-term directional plays' },
    reversal: { name: 'Mean Reversion', icon: 'RefreshCw', desc: 'Oversold/overbought reversals' },
    volatility: { name: 'Volatility', icon: 'Activity', desc: 'Breakout and bands strategies' }
};

export const TABS = [
    { id: 'develop', label: 'DEVELOP' },
    { id: 'tearsheet', label: 'TEARSHEET' },
    { id: 'portfolio', label: 'PORTFOLIO' },
    { id: 'paper', label: 'PAPER' },
    { id: 'composer', label: 'COMPOSE' },
    { id: 'validate', label: 'VALIDATE' },
    { id: 'replay', label: 'REPLAY' }
];
