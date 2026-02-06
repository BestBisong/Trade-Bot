import pandas as pd
import numpy as np
import logging
from sklearn.ensemble import RandomForestClassifier

class MLStrategy:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        self.is_trained = False
        self.feature_columns = ["returns", "volatility", "atr", "regime"]

    def prepare_features(self, df):
        if df is None or len(df) < 30: # Safety guard for small data
            return pd.DataFrame()
            
        df = df.copy()
        df["returns"] = df["close"].pct_change()
        df["volatility"] = df["returns"].rolling(20).std()
        
        # ATR Calculation
        high_low = df['high'] - df['low']
        high_cp = np.abs(df['high'] - df['close'].shift())
        low_cp = np.abs(df['low'] - df['close'].shift())
        df['atr'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(14).mean()
        
        df["vol_avg"] = df["volatility"].rolling(100).mean()
        df["regime"] = np.where(df["volatility"] > df["vol_avg"], 1, 0)
        df["target"] = np.where(df["close"].shift(-3) > df["close"], 1, 0)
        
        return df.dropna()

    def train(self, df_list):
        combined_data = []
        for df in df_list:
            prepared = self.prepare_features(df)
            if not prepared.empty: combined_data.append(prepared)
            
        if combined_data:
            all_data = pd.concat(combined_data)
            self.model.fit(all_data[self.feature_columns], all_data["target"])
            self.is_trained = True
            logging.info("ML_TRAIN: Model updated.")

    def signal(self, df):
        if not self.is_trained: return "HOLD"
        processed_df = self.prepare_features(df)
        if processed_df.empty: return "HOLD"
            
        current_features = processed_df[self.feature_columns].iloc[-1:]
        # Confidence threshold lowered to 0.55 for more active trading
        probs = self.model.predict_proba(current_features)[0]
        return "BUY" if probs[1] > 0.55 else "HOLD"