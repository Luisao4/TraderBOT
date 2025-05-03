import pandas as pd
import numpy as np

def calculate_atr(data, atr_length=96):
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift(1))
    low_close = np.abs(data['low'] - data['close'].shift(1))
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.ewm(span=atr_length, adjust=False).mean()  # Wilder’s smoothing
    return atr

def moving_average(series, length, ma_type="EMA"):
    if ma_type == "SMA":
        return series.rolling(window=length, min_periods=1).mean()
    elif ma_type == "EMA":
        return series.ewm(span=length, adjust=False).mean()
    elif ma_type == "WMA":
        weights = np.arange(1, length + 1)
        return series.rolling(window=length, min_periods=1).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
    else:
        return series  # No transformation

def calculate_atr_and_emas(data, atr_length=96, ema_short=24, ema_long=42):
    """
    Calculate ATR, EMA 24, and EMA 42 from OHLC data.
    
    Args:
        data (pd.DataFrame): DataFrame with 'high', 'low', 'close' columns.
        atr_length (int): ATR period (default: 96).
        ema_short (int): Short EMA period (default: 24).
        ema_long (int): Long EMA period (default: 42).
    
    Returns:
        tuple: (atr, ema_24, ema_42) as pd.Series objects.
    """
    if not all(col in data.columns for col in ['high', 'low', 'close']):
        raise ValueError("DataFrame must contain 'high', 'low', 'close' columns")
    
    atr = calculate_atr(data, atr_length)
    ema_24 = moving_average(data['close'], ema_short, "EMA")
    ema_42 = moving_average(data['close'], ema_long, "EMA")
    
    return atr, ema_24, ema_42