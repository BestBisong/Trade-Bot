import pandas as pd
import numpy as np
import logging
from sklearn.ensemble import RandomForestClassifier

class MLStrategy:
    def __init__(self):
        # Increased estimators and depth for professional pattern recognition
        self.model = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42)
        self.is_trained = False
        self.feature_columns = ["returns", "volatility", "atr", "regime", "rsi", "mfi"]

    def prepare_features(self, df):
        if df is None or len(df) < 100: 
            return pd.DataFrame()
            
        df = df.copy()
        df["returns"] = df["close"].pct_change()
        df["volatility"] = df["returns"].rolling(20).std()
        
        # ATR Calculation
        high_low = df['high'] - df['low']
        high_cp = np.abs(df['high'] - df['close'].shift())
        low_cp = np.abs(df['low'] - df['close'].shift())
        df['atr'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(14).mean()
        
        # RSI Implementation
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss + 0.00001))) # Avoid div by zero

        # Money Flow Index (MFI) approximation
        tp = (df['high'] + df['low'] + df['close']) / 3
        mf = tp * df['volume']
        df['mfi'] = mf.rolling(14).mean() / mf.rolling(50).mean()
        
        df["vol_avg"] = df["volatility"].rolling(100).mean()
        df["regime"] = np.where(df["volatility"] > df["vol_avg"], 1, 0)
        
        # Target: Predict if price will rise 0.5% in next 5 candles
        df["target"] = np.where(df["close"].shift(-5) > (df["close"] * 1.005), 1, 0)
        
        return df.dropna()

    def train(self, df_list):
        combined_data = []
        for df in df_list:
            prepared = self.prepare_features(df)
            if not prepared.empty: combined_data.append(prepared)
            
        if combined_data:
            all_data = pd.concat(combined_data)
            if len(all_data['target'].unique()) > 1:
                self.model.fit(all_data[self.feature_columns], all_data["target"])
                self.is_trained = True
                logging.info(f"ML_TRAIN: Model trained on {len(all_data)} samples.")

    def signal(self, df):
        if not self.is_trained: return "HOLD"
        processed_df = self.prepare_features(df)
        if processed_df.empty: return "HOLD"
            
        current_features = processed_df[self.feature_columns].iloc[-1:]
        probs = self.model.predict_proba(current_features)[0]
        return "BUY" if probs[1] > 0.60 else "HOLD"