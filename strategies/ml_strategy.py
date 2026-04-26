import pandas as pd
import numpy as np
import logging, joblib, os
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler

class MLStrategy:
    def __init__(self, model_path="trading_model.joblib"):
        self.model_path = model_path
        self.feature_columns = ["returns", "volatility", "atr", "rsi", "trend", "volume_z", "bb_width"]
        self.scaler = StandardScaler()
        self.is_trained = False
        self.scaler_fitted = False
        self.last_train_index = None
        self.classes_ = np.array([0, 1])
        self.min_train_samples = 80
        
        if os.path.exists(self.model_path):
            try:
                data = joblib.load(self.model_path)
                self.model = data['model']
                self.scaler = data.get('scaler', StandardScaler())
                self.scaler_fitted = data.get('scaler_fitted', True)
                self.last_train_index = data.get('last_train_index')
                self.is_trained = True
                logging.info("JARVIS | Brain Loaded.")
            except: self._init_fresh()
        else: self._init_fresh()

    def _init_fresh(self):
        self.model = SGDClassifier(
            loss='log_loss',
            random_state=42,
            alpha=0.0005,
            penalty='l2',
            max_iter=1000,
            tol=1e-3,
        )
        self.scaler = StandardScaler()
        self.scaler_fitted = False
        self.is_trained = False
        self.last_train_index = None
        logging.info("JARVIS | Learning from scratch.")

    def _compute_base_features(self, df):
        if df is None or len(df) < 50:
            return pd.DataFrame()

        out = df.copy()
        out["returns"] = out["close"].pct_change()
        out["volatility"] = out["returns"].rolling(20).std()
        out["atr"] = (out["high"] - out["low"]).rolling(14).mean()
        out["trend"] = np.where(out["close"] > out["close"].rolling(50).mean(), 1, -1)
        out["volume_z"] = (out["volume"] - out["volume"].rolling(30).mean()) / (out["volume"].rolling(30).std() + 1e-9)

        mid = out["close"].rolling(20).mean()
        stdev = out["close"].rolling(20).std()
        out["bb_width"] = ((mid + 2 * stdev) - (mid - 2 * stdev)) / (mid + 1e-9)

        delta = out["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        out["rsi"] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        return out

    def prepare_training_features(self, df):
        prepared = self._compute_base_features(df)
        if prepared.empty:
            return pd.DataFrame()

        # Target: Did price move up in the next 3 candles?
        prepared["target"] = np.where(prepared["close"].shift(-3) > prepared["close"], 1, 0)
        return prepared.dropna()

    def prepare_inference_features(self, df):
        prepared = self._compute_base_features(df)
        if prepared.empty:
            return pd.DataFrame()
        # Keep the latest fully formed indicator row; no forward target dependency.
        return prepared.dropna(subset=self.feature_columns)

    def continuous_learn(self, df):
        """Learn from the market character every session."""
        prepared = self.prepare_training_features(df)
        if prepared.empty or len(prepared) < self.min_train_samples:
            return

        latest_index = str(prepared.index[-1])
        if latest_index == self.last_train_index:
            return

        X_raw = prepared[self.feature_columns]
        y = prepared["target"]

        self.scaler.partial_fit(X_raw)
        self.scaler_fitted = True
        X = self.scaler.transform(X_raw)
        
        if not self.is_trained:
            self.model.partial_fit(X, y, classes=self.classes_)
            self.is_trained = True
        else:
            self.model.partial_fit(X, y)

        self.last_train_index = latest_index
        self.is_trained = True
        self.save_brain()

    def signal(self, df):
        if not self.is_trained or not self.scaler_fitted:
            return "HOLD"

        prepared = self.prepare_inference_features(df)
        if prepared.empty:
            return "HOLD"
        
        X = self.scaler.transform(prepared[self.feature_columns].iloc[-1:])
        prob = self.model.predict_proba(X)[0][1]
        
        if prob > 0.60:
            return "BUY"
        if prob < 0.40:
            return "SELL"
        return "HOLD"

    def confidence(self, df):
        if not self.is_trained or not self.scaler_fitted:
            return 0.5
        prepared = self.prepare_inference_features(df)
        if prepared.empty:
            return 0.5
        X = self.scaler.transform(prepared[self.feature_columns].iloc[-1:])
        return float(self.model.predict_proba(X)[0][1])

    def learn_from_settlement(self, df, label=None, pnl=None):
        # Keeps API compatibility while routing to incremental learning.
        self.continuous_learn(df)

    def save_brain(self):
        joblib.dump(
            {
                'model': self.model,
                'scaler': self.scaler,
                'scaler_fitted': self.scaler_fitted,
                'last_train_index': self.last_train_index,
            },
            self.model_path,
        )