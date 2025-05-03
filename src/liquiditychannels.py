# src/liquiditychannels.py
import pandas as pd

# Inputs
ps = 15
exag = 5
del_after = 500
del_untouched = True
hide_channel = False

class Liquidity:
    def __init__(self):
        self.price = []
        self.idx = []
        self.hrz = []
        self.diag = []

    def add_liq(self, price, idx, bull, bar_index, atr, exag):
        self.price.append(price)
        self.idx.append(idx)
        self.hrz.append((idx, price, bar_index, price))
        if not hide_channel:
            y2 = price + (1 if bull else -1) * (bar_index - idx) * atr.iloc[bar_index] * exag
            self.diag.append((idx, price, bar_index, y2))

    def update_liq(self, bull, bar_index, atr, exag, high, low, del_after, del_untouched):
        i = len(self.price) - 1
        while i >= 0:
            idx, price = self.idx[i], self.price[i]
            self.hrz[i] = (idx, price, bar_index, price)
            if not hide_channel:
                y2 = price + (1 if bull else -1) * (bar_index - idx) * atr.iloc[bar_index] * exag
                self.diag[i] = (idx, price, bar_index, y2)
            old = (bar_index - idx >= del_after)
            crossed = bull and high.iloc[bar_index] > price or not bull and low.iloc[bar_index] < price
            if old or (del_untouched and crossed):
                del self.price[i]
                del self.idx[i]
                del self.hrz[i]
                if not hide_channel:
                    del self.diag[i]
            i -= 1

def is_pivot(df, i, ps, is_high=True):
    if i < ps:
        return False
    prices = df['high'] if is_high else df['low']
    window = prices.iloc[i - ps:i + 1]
    current = prices.iloc[i]
    return is_high and current == window.max() or not is_high and current == window.min()

# Mock ATR function for testing (since src.atr isn't available)
def calculate_mock_atr(df, period=14):
    # Simple mock: use high-low range as a proxy for ATR
    tr = df['high'] - df['low']
    return tr.rolling(window=period, min_periods=1).mean()

def calculate_liquidity_channels_incremental(df, current_idx, bsl=None, ssl=None, atr=None, ps=ps, exag=exag, del_after=del_after, del_untouched=del_untouched, hide_channel=hide_channel):
    if not all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        raise ValueError("DataFrame must contain 'open', 'high', 'low', 'close' columns")

    # Initialize if not provided
    if bsl is None:
        bsl = Liquidity()
    if ssl is None:
        ssl = Liquidity()
    if atr is None:
        atr = calculate_mock_atr(df)  # Use mock ATR if none provided

    # Process up to current_idx using sliced df but full atr
    df_slice = df.iloc[:current_idx + 1]
    for i in range(len(df_slice)):
        if is_pivot(df_slice, i, ps, is_high=True):
            bsl.add_liq(df_slice['high'].iloc[i], i, True, i, atr, exag)
        if is_pivot(df_slice, i, ps, is_high=False):
            ssl.add_liq(df_slice['low'].iloc[i], i, False, i, atr, exag)
        bsl.update_liq(True, i, atr, exag, df['high'], df['low'], del_after, del_untouched)
        ssl.update_liq(False, i, atr, exag, df['high'], df['low'], del_after, del_untouched)

    return bsl.hrz, bsl.diag, ssl.hrz, ssl.diag, bsl, ssl, atr

def get_next_level(bar_index, hrz_lines):
    valid_levels = [line for line in hrz_lines if line[0] <= bar_index and line[2] >= bar_index]
    if not valid_levels:
        return None
    return sorted(valid_levels, key=lambda x: x[1])[0][1]

# Test code to run directly
if __name__ == "__main__":
    # Sample OHLC data
    data = {
        'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        'high': [101, 103, 104, 102, 106, 107, 108, 109, 110, 111],
        'low': [99, 100, 101, 100, 102, 103, 104, 105, 106, 107],
        'close': [100, 102, 103, 101, 105, 106, 107, 108, 109, 110]
    }
    df = pd.DataFrame(data)

    # Run the function
    bsl_hrz, bsl_diag, ssl_hrz, ssl_diag, bsl, ssl, atr = calculate_liquidity_channels_incremental(
        df=df,
        current_idx=len(df) - 1,  # Process all data
        ps=3,  # Smaller ps for shorter sample data
    )

    # Print results
    print("Bull Horizontal Levels:", bsl_hrz)
    print("Bull Diagonal Levels:", bsl_diag)
    print("Bear Horizontal Levels:", ssl_hrz)
    print("Bear Diagonal Levels:", ssl_diag)
    print("Next Bull Level at index 5:", get_next_level(5, bsl_hrz))
    print("Next Bear Level at index 5:", get_next_level(5, ssl_hrz))