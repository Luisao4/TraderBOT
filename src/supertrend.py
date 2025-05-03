import pandas as pd
import numpy as np

def get_supertrend(high, low, close, lookback, multiplier):
    """
    Calculate Supertrend indicator with trend direction.
    
    Args:
        high (pd.Series): High prices.
        low (pd.Series): Low prices.
        close (pd.Series): Close prices.
        lookback (int): ATR lookback period (e.g., 96).
        multiplier (int): ATR multiplier (e.g., 3).
    
    Returns:
        tuple: (supertrend_values, trend_direction)
            - supertrend_values: Series of Supertrend values (upper/lower band).
            - trend_direction: Series of 1 (uptrend), -1 (downtrend), or 0 (neutral).
    """
    # ATR Calculation
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=lookback, adjust=False).mean()  # Wilder’s smoothing
    
    # H/L Average and Basic Bands
    hl_avg = (high + low) / 2
    upper_band = hl_avg + multiplier * atr
    lower_band = hl_avg - multiplier * atr
    
    # Initialize final bands and Supertrend
    final_upper = pd.Series(index=high.index, dtype=float)
    final_lower = pd.Series(index=high.index, dtype=float)
    supertrend_values = pd.Series(index=high.index, dtype=float)
    trend_direction = pd.Series(index=high.index, dtype=int)
    
    # Loop to calculate final bands and Supertrend (keeping your logic)
    for i in range(len(high)):
        if i == 0:
            final_upper.iloc[i] = 0
            final_lower.iloc[i] = 0
            supertrend_values.iloc[i] = 0
            trend_direction.iloc[i] = 0  # Neutral start
        else:
            # Final Upper Band
            if (upper_band.iloc[i] < final_upper.iloc[i-1]) or (close.iloc[i-1] > final_upper.iloc[i-1]):
                final_upper.iloc[i] = upper_band.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i-1]
                
            # Final Lower Band
            if (lower_band.iloc[i] > final_lower.iloc[i-1]) or (close.iloc[i-1] < final_lower.iloc[i-1]):
                final_lower.iloc[i] = lower_band.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i-1]
                
            # Supertrend Logic
            if i == 1:  # After first bar, initialize based on close
                if close.iloc[i] > final_upper.iloc[i]:
                    supertrend_values.iloc[i] = final_lower.iloc[i]
                else:
                    supertrend_values.iloc[i] = final_upper.iloc[i]
            elif supertrend_values.iloc[i-1] == final_upper.iloc[i-1] and close.iloc[i] < final_upper.iloc[i]:
                supertrend_values.iloc[i] = final_upper.iloc[i]
            elif supertrend_values.iloc[i-1] == final_upper.iloc[i-1] and close.iloc[i] > final_upper.iloc[i]:
                supertrend_values.iloc[i] = final_lower.iloc[i]
            elif supertrend_values.iloc[i-1] == final_lower.iloc[i-1] and close.iloc[i] > final_lower.iloc[i]:
                supertrend_values.iloc[i] = final_lower.iloc[i]
            elif supertrend_values.iloc[i-1] == final_lower.iloc[i-1] and close.iloc[i] < final_lower.iloc[i]:
                supertrend_values.iloc[i] = final_upper.iloc[i]
            
            # Trend Direction
            if supertrend_values.iloc[i] == 0:  # Handle initial neutral
                trend_direction.iloc[i] = 0
            elif close.iloc[i] > supertrend_values.iloc[i]:
                trend_direction.iloc[i] = 1  # Uptrend (LONG)
            elif close.iloc[i] < supertrend_values.iloc[i]:
                trend_direction.iloc[i] = -1  # Downtrend (SHORT)
            else:
                trend_direction.iloc[i] = 0  # Neutral (rare edge case)
    
    # Drop NaNs and first row (consistent with original)
    valid_idx = supertrend_values.dropna().index[1:]
    supertrend_values = supertrend_values.loc[valid_idx]
    trend_direction = trend_direction.loc[valid_idx]
    
    return supertrend_values, trend_direction

