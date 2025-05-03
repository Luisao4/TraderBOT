# Bitcoin Trading Bot

This project is an automated trading bot for Bitcoin (BTC) that uses technical indicators such as Average True Range (ATR), Exponential Moving Averages (EMAs), Supertrend, and liquidity channels to generate trading signals. It fetches hourly OHLC (Open, High, Low, Close) data from the CoinGecko API, stores it in a MySQL database, and executes trades with risk management. The bot sends trade notifications via Telegram and supports visualization of price data through candlestick charts.

## Features
- **Data Fetching**: Retrieves hourly Bitcoin OHLC data using the CoinGecko Pro API.
- **Technical Indicators**: Calculates ATR, short/long EMAs, Supertrend, and liquidity-based signals.
- **Trading Logic**: Executes long/short trades based on indicator signals with a fixed risk-reward ratio (1.5).
- **Database Storage**: Stores trade data, equity curve, and parameters in a MySQL database.
- **Notifications**: Sends trade updates (entry, exit, P/L) via Telegram.
- **Visualization**: Plots candlestick charts using `mplfinance`.
- **Indicator Logging**: Prints current indicator values (ATR, EMAs, Supertrend, trend direction) for Rate of Change (ROC) analysis.

## Project Structure
```
project_root/
├── .env                   # Environment variables (excluded from Git)
├── .gitignore             # Git ignore file
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
├── main.py                # Main trading bot script
└── src/
    ├── fetch_data.py      # Fetches and stores OHLC data
    ├── plot.py            # Plots candlestick charts
    ├── atr.py             # ATR and EMA calculations
    ├── supertrend.py      # Supertrend indicator
    ├── liquiditychannels.py # Liquidity channel calculations
```

## Prerequisites
- **Python 3.8+**
- **MySQL Server**: A running MySQL instance for storing data.
- **CoinGecko Pro API Key**: Required for fetching OHLC data.
- **Telegram Bot**: A Telegram bot token and chat ID for notifications.
- **Git**: For cloning the repository.

## Setup
1. **Clone the Repository**:
   ```bash
   git clone <your-repo-url>
   cd <repository-name>
   ```

2. **Install Dependencies**:
   Install the required Python packages listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up MySQL Database**:
   - Create a MySQL database named `NS_tradingBOT`.
   - Ensure your MySQL user has appropriate permissions.

4. **Create `.env` File**:
   In the project root, create a `.env` file with the following content:
   ```
   DB_HOST=localhost
   DB_USER=<your-mysql-user>
   DB_PASSWORD=<your-mysql-password>
   DB_DATABASE=NS_tradingBOT
   TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>
   TELEGRAM_CHAT_ID=<your-telegram-chat-id>
   COINGECKO_API_KEY=<your-coingecko-api-key>
   ```
   Replace placeholders with your actual credentials. **Do not commit `.env` to Git.**

5. **Verify Setup**:
   Ensure MySQL is running and the `.env` file is correctly configured.

## Usage
### 1. Fetch OHLC Data
Run `fetch_data.py` to retrieve Bitcoin OHLC data from CoinGecko and store it in the MySQL database:
```bash
python src/fetch_data.py
```
This script fetches data from the last known timestamp or the past 2 hours if no data exists.

### 2. Run the Trading Bot
Run `main.py` to execute the trading bot:
```bash
python main.py
```
The bot:
- Creates necessary database tables (`Trades`, `EquityCurve`, `Parameters`).
- Fetches recent data via `fetch_data.py`.
- Generates trading signals using hardcoded parameters.
- Manages positions (open/close trades) with 2% risk per trade.
- Sends Telegram notifications for trade events.
- Prints indicator values (ATR, EMAs, Supertrend, trend direction) for each run, useful for ROC analysis.
- Logs equity and parameters to the database.

To log indicator values for later analysis:
```bash
python main.py >> indicators.log
```

### 3. Visualize Price Data
Run `plot.py` to generate a candlestick chart of Bitcoin prices:
```bash
python src/plot.py
```
This script fetches OHLC data from the database and displays a chart using `mplfinance`.

## Indicator Output
Each run of `main.py` prints the current values of key indicators for the latest data point:
```
Indicator Values at <timestamp>:
ATR (atr_96): <value>
EMA Short: <value>
EMA Long: <value>
Supertrend: <value>
Trend Direction: <value> (1=Up, -1=Down, 0=Neutral)
```
These values can be logged to a file (e.g., `indicators.log`) for Rate of Change (ROC) analysis.

## Contributing
Contributions are welcome! Please:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes (`git commit -m 'Add your feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request.

## License
[Specify your license, e.g., MIT License. Replace this text with your chosen license or leave as TBD.]

## Notes
- Ensure the `.env` file is never committed to Git (it’s excluded via `.gitignore`).
- The bot uses hardcoded parameters in `main.py`. Uncomment the Bayesian optimization code for parameter tuning (requires `scikit-optimize`).
- Test the bot in a simulated environment before using real funds.
- Monitor Telegram notifications for trade updates.

For issues or questions, please open an issue on GitHub.