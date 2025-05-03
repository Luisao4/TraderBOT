from dotenv import load_dotenv
import os
import requests
import pymysql
from datetime import datetime, timedelta, UTC
from decimal import Decimal  # For precise decimal arithmetic

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

# CoinGecko API configuration
COINGECKO_API_URL_PRO = "https://pro-api.coingecko.com/api/v3"
API_KEY = os.getenv("COINGECKO_API_KEY")
coin_id = "bitcoin"  # Only Bitcoin
vs_currency = "usd"  # Target currency

# Function to fetch OHLC data
def fetch_ohlc_data(from_timestamp, to_timestamp):
    """Fetch OHLC data from CoinGecko API for Bitcoin"""
    try:
        response = requests.get(
            f"{COINGECKO_API_URL_PRO}/coins/{coin_id}/ohlc/range?vs_currency={vs_currency}&from={from_timestamp}&to={to_timestamp}&interval=hourly",
            headers={
                "accept": "application/json",
                "x-cg-pro-api-key": API_KEY
            },
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"API error for {coin_id}: {str(e)}")
        return []

# Function to save OHLC data to MySQL
def save_ohlc_to_db(data):
    """Save OHLC data to the btc1h table with batch insert"""
    conn = None
    cursor = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO btc1h (token_id, timestamp, open, high, low, close)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            open = VALUES(open),
            high = VALUES(high),
            low = VALUES(low),
            close = VALUES(close)
        """
        # Prepare data for insertion
        insert_data = []
        for row in data:
            timestamp = int(row[0] / 1000)  # Convert from milliseconds to seconds
            open_price = float(row[1])
            high_price = float(row[2])
            low_price = float(row[3])
            close_price = float(row[4])
            insert_data.append((coin_id, timestamp, open_price, high_price, low_price, close_price))

        # Insert data into the database
        cursor.executemany(insert_query, insert_data)
        conn.commit()
        print(f"Saved {len(insert_data)} OHLC records for {coin_id}")
    except pymysql.Error as err:
        print(f"MySQL Error: {err}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Function to fetch the latest timestamp from the database
def fetch_latest_timestamp_from_db():
    """Fetch the latest timestamp for Bitcoin from the btc1h table"""
    conn = None
    cursor = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """
        SELECT MAX(timestamp) AS latest_timestamp 
        FROM btc1h 
        WHERE token_id = %s
        """
        cursor.execute(query, (coin_id,))
        result = cursor.fetchone()
        return result['latest_timestamp'] if result['latest_timestamp'] else None
    except pymysql.Error as err:
        print(f"MySQL Error: {err}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Main function to run the script
def main():
    # Fetch the latest timestamp from the database
    latest_timestamp = fetch_latest_timestamp_from_db()
    if latest_timestamp:
        print(f"Latest timestamp in database for {coin_id}: {latest_timestamp}")
    else:
        print(f"No data found in database for {coin_id}. Fetching last 2 hours of data.")

    # Calculate the start and end timestamps for the API request
    end_timestamp = int(datetime.now().timestamp())  # Current time as the end timestamp
    from_timestamp = latest_timestamp if latest_timestamp else int((datetime.now() - timedelta(hours=2)).timestamp())

    # Fetch OHLC data from the API
    ohlc_data = fetch_ohlc_data(from_timestamp, end_timestamp)
    if not ohlc_data:
        print(f"No OHLC data found for {coin_id}. Skipping.")
        return

    # Save OHLC data to the database
    save_ohlc_to_db(ohlc_data)

if __name__ == "__main__":
    main()