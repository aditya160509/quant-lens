import pandas as pd
import numpy as np

def compute_indicators(ticker, start_date, end_date, df=None):
    """
    Compute technical indicators for a given ticker.
    If df is provided, use it directly.
    Returns a dictionary of indicator series.
    """
    if df is None or df.empty:
        return {}

    # Ensure we have enough data
    # Calculate indicators
    indicators = {}
    
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']
    
    # 1. RSI (14)
    indicators['rsi'] = calculate_rsi(close, window=14)
    
    # 2. MACD (12, 26, 9)
    macd, signal, hist = calculate_macd(close, fast=12, slow=26, signal=9)
    indicators['macd'] = {
        "macd": macd,
        "signal": signal,
        "hist": hist
    }
    
    # 3. Stochastic (14, 3, 3)
    k, d = calculate_stoch(high, low, close, k_window=14, d_window=3, slow_k=3)
    indicators['stoch'] = {
        "k": k,
        "d": d
    }
    
    # 4. ROC (10)
    indicators['roc'] = calculate_roc(close, window=10)
    
    # 5. CCI (20)
    indicators['cci'] = calculate_cci(high, low, close, window=20)
    
    # 6. ADX (14)
    indicators['adx'] = calculate_adx(high, low, close, window=14)
    
    # 7. MFI (14)
    indicators['mfi'] = calculate_mfi(high, low, close, volume, window=14)
    
    return indicators

def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

def calculate_stoch(high, low, close, k_window=14, d_window=3, slow_k=3):
    low_min = low.rolling(window=k_window).min()
    high_max = high.rolling(window=k_window).max()
    
    k_fast = 100 * (close - low_min) / (high_max - low_min)
    k = k_fast.rolling(window=slow_k).mean()
    d = k.rolling(window=d_window).mean()
    return k, d

def calculate_roc(series, window=10):
    return ((series - series.shift(window)) / series.shift(window)) * 100

def calculate_cci(high, low, close, window=20):
    tp = (high + low + close) / 3
    sma = tp.rolling(window=window).mean()
    mad = tp.rolling(window=window).apply(lambda x: np.abs(x - x.mean()).mean())
    cci = (tp - sma) / (0.015 * mad)
    return cci

def calculate_adx(high, low, close, window=14):
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr1 = pd.DataFrame(high - low)
    tr2 = pd.DataFrame(abs(high - close.shift(1)))
    tr3 = pd.DataFrame(abs(low - close.shift(1)))
    frames = [tr1, tr2, tr3]
    tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
    atr = tr.rolling(window).mean()
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/window).mean() / atr)
    minus_di = 100 * (abs(minus_dm).ewm(alpha=1/window).mean() / atr)
    dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
    adx = dx.ewm(alpha=1/window).mean()
    return adx

def calculate_mfi(high, low, close, volume, window=14):
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    
    positive_flow = []
    negative_flow = []
    
    for i in range(len(typical_price)):
        if i == 0:
            positive_flow.append(0)
            negative_flow.append(0)
            continue
            
        if typical_price.iloc[i] > typical_price.iloc[i-1]:
            positive_flow.append(money_flow.iloc[i])
            negative_flow.append(0)
        elif typical_price.iloc[i] < typical_price.iloc[i-1]:
            positive_flow.append(0)
            negative_flow.append(money_flow.iloc[i])
        else:
            positive_flow.append(0)
            negative_flow.append(0)
            
    positive_mf = pd.Series(positive_flow, index=typical_price.index).rolling(window=window).sum()
    negative_mf = pd.Series(negative_flow, index=typical_price.index).rolling(window=window).sum()
    
    mfi = 100 - (100 / (1 + positive_mf / negative_mf))
    return mfi
