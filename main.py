from dotenv import load_dotenv
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from sqlalchemy import create_engine, text
# from skopt import gp_minimize  # Commented out for future use
# from skopt.space import Integer  # Commented out for future use
from src.fetch_data import DB_CONFIG, main as fetch_data_main
from src.atr import calculate_atr, calculate_atr_and_emas
from src.supertrend import get_supertrend
from src.liquiditychannels import Liquidity, is_pivot, get_next_level

# Load environment variables
load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_DATABASE")
}

# Database connection
engine = create_engine(f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")

# Forward testing variables
INITIAL_EQUITY = 1000
open_position = None

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def create_tables():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Trades (
                trade_id INT AUTO_INCREMENT PRIMARY KEY,
                entry_time DATETIME,
                entry_price FLOAT,
                exit_time DATETIME,
                exit_price FLOAT,
                direction VARCHAR(10),
                outcome VARCHAR(10),
                r_achieved FLOAT,
                duration INT,
                status VARCHAR(10) DEFAULT 'OPEN'
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS EquityCurve (
                timestamp DATETIME PRIMARY KEY,
                equity FLOAT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Parameters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME,
                atr_length INT,
                ema_short INT,
                ema_long INT,
                supertrend_lookback INT,
                supertrend_multiplier INT,
                ps INT,
                exag INT,
                atr_threshold INT,
                impulse_scale INT,
                del_after INT
            )
        """))
        conn.commit()

def fetch_db_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    query = """
    SELECT timestamp, open, high, low, close
    FROM btc1h
    WHERE token_id = 'bitcoin' AND timestamp >= %s AND timestamp <= %s
    ORDER BY timestamp ASC
    """
    df = pd.read_sql(query, engine, params=(int(start_date.timestamp()), int(end_date.timestamp())))
    if df['timestamp'].duplicated().any():
        df = df.drop_duplicates(subset='timestamp', keep='first')
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('timestamp', inplace=True)
    return df

# Commented out for future use: Bayesian optimization functions
"""
def simulate_trades(df, params, initial_equity=10000, risk_per_trade=0.02, daily_loss_cap=0.04, use_fixed_rr=True, fixed_rr=1.5, max_duration=48):
    atr_96, ema_short, ema_long = calculate_atr_and_emas(df, atr_length=params['atr_length'], 
                                                        ema_short=params['ema_short'], ema_long=params['ema_long'])
    supertrend, trend = get_supertrend(df['high'], df['low'], df['close'], lookback=params['supertrend_lookback'], 
                                      multiplier=params['supertrend_multiplier'])
    atr_full = calculate_atr(df, atr_length=params['atr_length']).bfill()
    high_series = df['high']
    low_series = df['low']

    df = df.copy()
    df['atr_96'] = atr_96
    df['ema_short'] = ema_short
    df['ema_long'] = ema_long
    df['supertrend'] = supertrend
    df['trend'] = trend

    trades = []
    equity = initial_equity
    daily_loss = 0
    last_day = None
    equity_curve = [equity]
    
    bsl = Liquidity()
    ssl = Liquidity()

    for i in range(len(df) - 1):
        row = df.iloc[i]
        current_day = row.name.date()

        if i >= params['ps']:
            if is_pivot(df, i, params['ps'], is_high=True):
                bsl.add_liq(df['high'].iloc[i], i, True, i, atr_full, params['exag'])
            if is_pivot(df, i, params['ps'], is_high=False):
                ssl.add_liq(df['low'].iloc[i], i, False, i, atr_full, params['exag'])

        bsl.update_liq(True, i, atr_full, params['exag'], high_series, low_series, params['del_after'], True)
        ssl.update_liq(False, i, atr_full, params['exag'], high_series, low_series, params['del_after'], True)

        if last_day != current_day:
            daily_loss = 0
            last_day = current_day

        if daily_loss >= daily_loss_cap * initial_equity or equity <= 0:
            equity_curve.append(equity)
            continue

        impulse = row['close'] - row['open'] > row['atr_96'] * params['impulse_scale']

        if (row['atr_96'] > params['atr_threshold'] and row['trend'] == 1 and row['ema_short'] > row['ema_long'] and impulse):
            entry_price = row['close']
            sl = row['supertrend']
            risk_distance = entry_price - sl
            if risk_distance < 1e-6:
                equity_curve.append(equity)
                continue
            tp = entry_price + risk_distance * fixed_rr if use_fixed_rr else get_next_level(i, bsl.hrz)
            if tp is None or sl >= entry_price or tp <= entry_price:
                equity_curve.append(equity)
                continue

            rr = (tp - entry_price) / (entry_price - sl)
            if rr < 1.5:
                equity_curve.append(equity)
                continue

            for j in range(i + 1, min(i + max_duration + 1, len(df))):
                future_row = df.iloc[j]
                if future_row['high'] >= tp:
                    exit_price = tp
                    outcome = 'win'
                    break
                elif future_row['low'] <= sl:
                    exit_price = sl
                    outcome = 'loss'
                    break
            else:
                equity_curve.append(equity)
                continue

            risk = equity * risk_per_trade
            size = risk / (entry_price - sl)
            profit = size * (exit_price - entry_price) if outcome == 'win' else size * (sl - entry_price)
            equity += profit
            equity = max(0, min(equity, 1e9))
            r_achieved = (exit_price - entry_price) / (entry_price - sl) if outcome == 'win' else -1
            daily_loss = max(0, daily_loss - profit)

            trades.append({
                'entry_time': row.name, 'entry_price': entry_price,
                'exit_time': future_row.name, 'exit_price': exit_price,
                'direction': 'LONG', 'outcome': outcome, 'r_achieved': r_achieved,
                'duration': (j - i) * 1
            })

        elif (row['atr_96'] > params['atr_threshold'] and row['trend'] == -1 and row['ema_short'] < row['ema_long'] and impulse):
            entry_price = row['close']
            sl = row['supertrend']
            risk_distance = sl - entry_price
            if risk_distance < 1e-6:
                equity_curve.append(equity)
                continue
            tp = entry_price - risk_distance * fixed_rr if use_fixed_rr else get_next_level(i, ssl.hrz)
            if tp is None or sl <= entry_price or tp >= entry_price:
                equity_curve.append(equity)
                continue

            rr = (entry_price - tp) / (sl - entry_price)
            if rr < 1.5:
                equity_curve.append(equity)
                continue

            for j in range(i + 1, min(i + max_duration + 1, len(df))):
                future_row = df.iloc[j]
                if future_row['low'] <= tp:
                    exit_price = tp
                    outcome = 'win'
                    break
                elif future_row['high'] >= sl:
                    exit_price = sl
                    outcome = 'loss'
                    break
            else:
                equity_curve.append(equity)
                continue

            risk = equity * risk_per_trade
            size = risk / (sl - entry_price)
            profit = size * (entry_price - exit_price) if outcome == 'win' else size * (entry_price - sl)
            equity += profit
            equity = max(0, min(equity, 1e9))
            r_achieved = (entry_price - exit_price) / (sl - entry_price) if outcome == 'win' else -1
            daily_loss = max(0, daily_loss - profit)

            trades.append({
                'entry_time': row.name, 'entry_price': entry_price,
                'exit_time': future_row.name, 'exit_price': exit_price,
                'direction': 'SHORT', 'outcome': outcome, 'r_achieved': r_achieved,
                'duration': (j - i) * 1
            })

        equity_curve.append(equity)

    return trades, equity_curve

def objective(params_list, df):
    params = {
        'atr_length': params_list[0], 'ema_short': params_list[1], 'ema_long': params_list[2],
        'supertrend_lookback': params_list[3], 'supertrend_multiplier': params_list[4],
        'ps': params_list[5], 'exag': params_list[6], 'atr_threshold': params_list[7],
        'impulse_scale': params_list[8], 'del_after': 500
    }
    if params['ema_short'] >= params['ema_long']:
        return 1e10
    trades, equity_curve = simulate_trades(df, params, use_fixed_rr=True, fixed_rr=1.5)
    final_equity = equity_curve[-1]
    wins = sum(1 for t in trades if t['outcome'] == 'win')
    win_rate = wins / len(trades) if trades else 0
    max_drawdown = max(0, (max(equity_curve) - min(equity_curve)) / max(equity_curve)) if max(equity_curve) > 0 else 1
    profit_factor = sum(t['r_achieved'] for t in trades if t['r_achieved'] > 0) / abs(sum(t['r_achieved'] for t in trades if t['r_achieved'] < 0)) if any(t['r_achieved'] < 0 for t in trades) else 1e10
    if not np.isfinite(final_equity) or not trades:
        return 1e10
    return -(profit_factor * win_rate / (1 + max_drawdown))

def optimize_inputs_bayesian(df, n_calls=50):
    space = [
        Integer(20, 150), Integer(5, 30), Integer(30, 100),
        Integer(10, 120), Integer(1, 3), Integer(5, 20),
        Integer(1, 10), Integer(10, 50), Integer(1, 2)
    ]
    res = gp_minimize(lambda x: objective(x, df), space, n_calls=n_calls, random_state=42)
    return {
        'atr_length': res.x[0], 'ema_short': res.x[1], 'ema_long': res.x[2],
        'supertrend_lookback': res.x[3], 'supertrend_multiplier': res.x[4],
        'ps': res.x[5], 'exag': res.x[6], 'atr_threshold': res.x[7],
        'impulse_scale': res.x[8], 'del_after': 500
    }
"""

def get_trading_signal(df, params):
    global open_position
    atr_96, ema_short, ema_long = calculate_atr_and_emas(df, atr_length=params['atr_length'], 
                                                        ema_short=params['ema_short'], ema_long=params['ema_long'])
    supertrend, trend = get_supertrend(df['high'], df['low'], df['close'], lookback=params['supertrend_lookback'], 
                                      multiplier=params['supertrend_multiplier'])
    df = df.copy()
    df['atr_96'] = atr_96
    df['ema_short'] = ema_short
    df['ema_long'] = ema_long
    df['supertrend'] = supertrend
    df['trend'] = trend

    latest_row = df.iloc[-1]
    impulse = latest_row['close'] - latest_row['open'] > latest_row['atr_96'] * params['impulse_scale']
    
    signal = "NO POSITION"
    if open_position:
        trade = open_position
        if trade['direction'] == 'LONG':
            if latest_row['low'] <= trade['sl']:
                signal = "CLOSE (Stop Loss Hit)"
            elif latest_row['high'] >= trade['tp']:
                signal = "CLOSE (Take Profit Hit)"
        elif trade['direction'] == 'SHORT':
            if latest_row['high'] >= trade['sl']:
                signal = "CLOSE (Stop Loss Hit)"
            elif latest_row['low'] <= trade['tp']:
                signal = "CLOSE (Take Profit Hit)"
    else:
        if (latest_row['atr_96'] > params['atr_threshold'] and latest_row['trend'] == 1 and 
            latest_row['ema_short'] > latest_row['ema_long'] and impulse):
            signal = "OPEN LONG"
        elif (latest_row['atr_96'] > params['atr_threshold'] and latest_row['trend'] == -1 and 
              latest_row['ema_short'] < latest_row['ema_long'] and impulse):
            signal = "OPEN SHORT"

    return signal, latest_row

def manage_position(signal, latest_row, params, equity):
    global open_position
    with engine.connect() as conn:
        if signal.startswith("CLOSE"):
            trade = open_position
            exit_price = latest_row['close']
            profit = (exit_price - trade['entry_price']) * trade['size'] if trade['direction'] == 'LONG' else (trade['entry_price'] - exit_price) * trade['size']
            r_achieved = (exit_price - trade['entry_price']) / (trade['entry_price'] - trade['sl']) if trade['direction'] == 'LONG' else (trade['entry_price'] - exit_price) / (trade['sl'] - trade['entry_price'])
            conn.execute(
                text("""
                    UPDATE Trades
                    SET exit_time = :exit_time, exit_price = :exit_price, outcome = :outcome,
                        r_achieved = :r_achieved, duration = :duration, status = 'CLOSED'
                    WHERE trade_id = :trade_id
                """),
                {
                    'exit_time': latest_row.name, 'exit_price': exit_price,
                    'outcome': 'win' if profit > 0 else 'loss', 'r_achieved': r_achieved,
                    'duration': int((latest_row.name - trade['entry_time']).total_seconds() / 3600),
                    'trade_id': trade['trade_id']
                }
            )
            conn.commit()
            equity += profit
            message = f"Closed {trade['direction']} trade: P/L = ${profit:.2f}, Equity = ${equity:.2f}"
            send_telegram_message(message)
            open_position = None
        elif signal.startswith("OPEN"):
            direction = signal.split()[1]
            entry_price = latest_row['close']
            sl = latest_row['supertrend']
            risk_distance = entry_price - sl if direction == 'LONG' else sl - entry_price
            tp = entry_price + risk_distance * 1.5 if direction == 'LONG' else entry_price - risk_distance * 1.5
            risk = equity * 0.02
            size = risk / risk_distance
            trade_data = {
                'entry_time': latest_row.name, 'entry_price': entry_price,
                'direction': direction, 'sl': sl, 'tp': tp, 'size': size
            }
            pd.DataFrame([trade_data]).to_sql('Trades', conn, if_exists='append', index=False)
            trade_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            trade_data['trade_id'] = trade_id
            open_position = trade_data
            equity -= risk
            message = (
                f"Opened {direction} trade:\n"
                f"Entry Price: ${entry_price:.2f}\n"
                f"Stop Loss: ${sl:.2f}\n"
                f"Take Profit: ${tp:.2f}\n"
                f"Equity: ${equity:.2f}"
            )
            send_telegram_message(message)
    return equity

def update_equity_curve(equity):
    with engine.connect() as conn:
        pd.DataFrame([{'timestamp': datetime.now(), 'equity': equity}]).to_sql('EquityCurve', conn, if_exists='append', index=False)
        conn.commit()

def hourly_main():
    global open_position
    equity = INITIAL_EQUITY
    create_tables()

    with engine.connect() as conn:
        open_trades = pd.read_sql("SELECT * FROM Trades WHERE status = 'OPEN'", conn)
        if not open_trades.empty:
            open_position = open_trades.iloc[0].to_dict()
            equity -= open_trades['size'] * (open_trades['entry_price'] - open_trades['sl']).abs().iloc[0]

    fetch_data_main()
    df = fetch_db_data()
    if df.empty:
        message = "No data fetched. Check database."
        send_telegram_message(message)
        return

    # Hardcoded best parameters
    best_params = {
        'atr_length': 29, 'ema_short': 28, 'ema_long': 56,
        'supertrend_lookback': 64, 'supertrend_multiplier': 3,
        'ps': 5, 'exag': 8, 'atr_threshold': 43,
        'impulse_scale': 2, 'del_after': 500
    }
    with engine.connect() as conn:
        pd.DataFrame([{'timestamp': datetime.now(), **best_params}]).to_sql('Parameters', conn, if_exists='append', index=False)
        conn.commit()

    signal, latest_row = get_trading_signal(df, best_params)
    
    # Print current indicator values for ROC analysis
    print(f"Indicator Values at {latest_row.name}:")
    print(f"ATR (atr_96): {latest_row['atr_96']:.2f}")
    print(f"EMA Short: {latest_row['ema_short']:.2f}")
    print(f"EMA Long: {latest_row['ema_long']:.2f}")
    print(f"Supertrend: {latest_row['supertrend']:.2f}")
    print(f"Trend Direction: {latest_row['trend']} (1=Up, -1=Down, 0=Neutral)")

    equity = manage_position(signal, latest_row, best_params, equity)
    update_equity_curve(equity)

    message = (
        f"Hourly Update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:\n"
        f"Signal: {signal}\n"
        f"Close Price: ${latest_row['close']:.2f}\n"
        f"Equity: ${equity:.2f}"
    )
    send_telegram_message(message)

if __name__ == "__main__":
    hourly_main()