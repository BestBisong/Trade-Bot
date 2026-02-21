import pandas as pd
import numpy as np
import logging
from sklearn.ensemble import RandomForestClassifier

class MLStrategy:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42)
        self.is_trained = False
        self.feature_columns = ["returns", "volatility", "atr", "regime", "rsi", "mfi"]

    def prepare_features(self, df):
        if df is None or len(df) < 100: return pd.DataFrame()
        df = df.copy()
        df["returns"] = df["close"].pct_change()
        df["volatility"] = df["returns"].rolling(20).std()
        
        # ATR and RSI calculations
        high_low = df['high'] - df['low']
        high_cp = np.abs(df['high'] - df['close'].shift())
        low_cp = np.abs(df['low'] - df['close'].shift())
        df['atr'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(14).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))

        # Money Flow Index (MFI)
        tp = (df['high'] + df['low'] + df['close']) / 3
        mf = tp * df['volume']
        df['mfi'] = mf.rolling(14).mean() / (mf.rolling(50).mean() + 1e-9)
        
        df["vol_avg"] = df["volatility"].rolling(100).mean()
        df["regime"] = np.where(df["volatility"] > df["vol_avg"], 1, 0)
        
        # Multi-Class Target: 1 (Up), -1 (Down), 0 (Hold)
        future_return = (df["close"].shift(-5) - df["close"]) / df["close"]
        df["target"] = 0
        df.loc[future_return > 0.003, "target"] = 1
        df.loc[future_return < -0.003, "target"] = -1
        
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
        prediction = self.model.predict(current_features)[0]
        probs = self.model.predict_proba(current_features)[0] # Confidence check
        
        # Mapping: Index 0=Sell(-1), Index 1=Hold(0), Index 2=Buy(1)
        if prediction == 1 and probs[2] > 0.55: return "BUY"
        if prediction == -1 and probs[0] > 0.55: return "SELL"
        return "HOLD"