import os
import json
import pandas as pd
import yfinance as yf
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self, tickers_path="data/idx_master_tickers.json"):
        self.tickers_path = tickers_path
        self.tickers_df = None
        self.load_tickers()

    def load_tickers(self):
        """Load tickers from master JSON (941 tickers) or CSV fallback."""
        target = self.tickers_path
        
        # Check if master JSON exists
        base_data_dir = os.path.dirname(target) if os.path.dirname(target) else "data"
        master_json = os.path.join(base_data_dir, "idx_master_tickers.json")
        if not os.path.exists(master_json):
            if os.path.exists("data/idx_master_tickers.json"):
                master_json = "data/idx_master_tickers.json"

        # If requested target is legacy idx_tickers.csv or target not found, prefer master JSON
        if os.path.exists(master_json) and ("idx_tickers.csv" in target or not os.path.exists(target)):
            target = master_json

        if os.path.exists(target):
            try:
                if target.endswith(".json"):
                    with open(target, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.tickers_df = pd.DataFrame(data)
                else:
                    self.tickers_df = pd.read_csv(target)
                self.tickers_df['ticker'] = self.tickers_df['ticker'].str.strip().str.upper()
                logger.info(f"Loaded {len(self.tickers_df)} tickers from {target}")
            except Exception as e:
                logger.error(f"Failed to read {target}: {e}")
                self.tickers_df = pd.DataFrame(columns=['ticker', 'name', 'sector'])
        else:
            logger.warning(f"Ticker file not found at {target}")
            self.tickers_df = pd.DataFrame(columns=['ticker', 'name', 'sector'])

    def get_ticker_meta(self, ticker):
        """Get metadata (name, sector) for a ticker."""
        clean_ticker = ticker.replace(".JK", "").strip().upper()
        if self.tickers_df is not None and not self.tickers_df.empty:
            match = self.tickers_df[self.tickers_df['ticker'] == clean_ticker]
            if not match.empty:
                return {
                    'name': match.iloc[0].get('name', clean_ticker),
                    'sector': match.iloc[0].get('sector', 'General')
                }
        return {'name': clean_ticker, 'sector': 'General'}

    def fetch_single_ticker(self, ticker, period="2y"):
        """Fetch historical daily data for a single ticker."""
        yf_symbol = f"{ticker}.JK" if not ticker.endswith(".JK") else ticker
        try:
            stock = yf.Ticker(yf_symbol)
            df = stock.history(period=period, auto_adjust=False)
            if df.empty:
                return ticker, None, "Insufficient data"
            df = df.dropna(subset=['Close'])
            if len(df) < 50:
                return ticker, None, "Insufficient data"
            return ticker, df, None
        except Exception as e:
            return ticker, None, str(e)

    def fetch_batch_concurrent(self, ticker_list=None, max_workers=16, period="2y"):
        """Fetch historical data for a list of tickers using ThreadPoolExecutor."""
        if ticker_list is None:
            if self.tickers_df is not None and not self.tickers_df.empty:
                ticker_list = self.tickers_df['ticker'].tolist()
            else:
                ticker_list = []

        results = {}
        total = len(ticker_list)
        logger.info(f"Starting batch fetch for {total} tickers with {max_workers} workers...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(self.fetch_single_ticker, ticker, period): ticker
                for ticker in ticker_list
            }

            for future in as_completed(future_to_ticker):
                ticker, df, err = future.result()
                if df is not None:
                    results[ticker] = df
                else:
                    logger.debug(f"Ticker {ticker} skipped: {err}")

        logger.info(f"Successfully fetched data for {len(results)}/{total} tickers.")
        return results
