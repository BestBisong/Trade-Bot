import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

import logging
import pandas as pd
from strategies.ml_strategy import MLStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(message)s", datefmt="%H:%M:%S")

DATA_DIR = "data"
TIMEFRAME = "15m"
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
TRAIN_FRACTION = 0.80
MAX_SAMPLES_PER_SYMBOL = 12000


def train_offline():
    ml_agent = MLStrategy(model_path="trading_model.joblib", load_pretrained=False)
    ml_agent._init_fresh()

    train_frames = []

    logging.info("Offline training with TP-before-SL labels (chronological split)...")

    for symbol in SYMBOLS:
        file_name = f"{symbol.replace('/', '_')}_{TIMEFRAME}.csv"
        file_path = os.path.join(DATA_DIR, file_name)

        if not os.path.exists(file_path):
            logging.warning("File not found: %s. Skipping.", file_path)
            continue

        df = pd.read_csv(file_path, parse_dates=["timestamp"])
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        if len(df) < 500:
            logging.warning("Insufficient candles in %s. Skipping.", file_name)
            continue

        split = int(len(df) * TRAIN_FRACTION)
        train_df = df.iloc[:split]
        prepared = ml_agent.prepare_training_features(train_df)
        if prepared.empty:
            logging.warning("No labeled samples for %s.", symbol)
            continue
        if len(prepared) > MAX_SAMPLES_PER_SYMBOL:
            prepared = prepared.iloc[-MAX_SAMPLES_PER_SYMBOL:]

        train_frames.append(prepared)
        logging.info("  %s: %s train samples (first %.0f%% of history)", symbol, len(prepared), TRAIN_FRACTION * 100)

    if not train_frames:
        logging.error("No training files processed.")
        return

    combined = pd.concat(train_frames)
    X_raw = combined[ml_agent.feature_columns]
    y = combined["target"]

    logging.info("Fitting on %s samples (long-win %.1f%%)...", len(combined), 100.0 * y.mean())
    ml_agent.scaler.fit(X_raw)
    ml_agent.scaler_fitted = True
    X = ml_agent.scaler.transform(X_raw)
    ml_agent.model.fit(X, y)
    ml_agent.is_trained = True
    ml_agent.save_brain()
    logging.info("Saved aligned model → trading_model.joblib")


if __name__ == "__main__":
    train_offline()
