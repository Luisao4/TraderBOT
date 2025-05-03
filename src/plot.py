from dotenv import load_dotenv
import os
import pymysql
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd

# Load environment variables
load_dotenv()

# MySQL database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_DATABASE"),
    "cursorclass": pymysql.cursors.DictCursor
}

# Function to fetch OHLC data from the database
def fetch_ohlc_data():
    """Fetch OHLC data from the btc1h table"""
    conn = None
    cursor = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """
        SELECT timestamp, open, high, low, close 
        FROM btc1h 
        WHERE token_id = 'bitcoin' 
        ORDER BY timestamp ASC
        """
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except pymysql.Error as err:
        print(f"MySQL Error: {err}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Function to plot candlestick chart
def plot_candlestick(data):
    """Plot candlestick chart using mplfinance"""
    if not data:
        print("No data to plot.")
        return

    # Convert data to a pandas DataFrame
    df = pd.DataFrame(data)

    # Ensure the OHLC columns are of type float
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)

    # Convert timestamp to datetime and set it as the index
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('timestamp', inplace=True)

    # Plot the candlestick chart
    mpf.plot(df, type='candle', style='charles', title='Bitcoin 1-Hour Candlestick Chart', volume=False)

# Main function to run the script
def main():
    # Fetch OHLC data from the database
    ohlc_data = fetch_ohlc_data()
    if not ohlc_data:
        print("No OHLC data found in the database.")
        return

    # Plot the candlestick chart
    plot_candlestick(ohlc_data)

if __name__ == "__main__":
    main()