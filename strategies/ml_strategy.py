import logging
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from strategies.execution_levels import label_tp_before_sl

# Label horizon: ~12h on 15m bars; matches typical hold before TP/SL
LABEL_MAX_BARS = 48
LABEL_SL_ATR_MULT = 2.0
LABEL_RR_RATIO = 1.0



class MLStrategy:
    def __init__(self, model_path="trading_model.joblib", load_pretrained=True):
        self.model_path = model_path
        self.feature_columns = [
            "returns",
            "volatility",
            "atr",
            "rsi",
            "trend",
            "volume_z",
            "bb_width",
        ]
        self.scaler = StandardScaler()
        self.is_trained = False
        self.scaler_fitted = False
        self.last_train_len = None
        self.min_train_samples = 120
        self.retrain_bar_gap = 288

        if load_pretrained and model_path and os.path.exists(model_path):
            try:
                data = joblib.load(model_path)
                self.model = data["model"]
                self.scaler = data.get("scaler", StandardScaler())
                self.scaler_fitted = data.get("scaler_fitted", True)
                self.last_train_len = data.get("last_train_len")
                self.is_trained = True
                logging.info("JARVIS | Brain loaded from %s", model_path)
            except Exception:
                self._init_fresh()
        else:
            self._init_fresh()

    def _init_fresh(self):
        self.model = RandomForestClassifier(
            n_estimators=120,
            max_depth=5,
            min_samples_leaf=8,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.scaler_fitted = False
        self.is_trained = False
        self.last_train_len = None
        logging.info("JARVIS | Fresh ML model initialized.")

    def _compute_base_features(self, df):
        if df is None or len(df) < 50:
            return pd.DataFrame()

        out = df.copy()
        out["returns"] = out["close"].pct_change()
        out["volatility"] = out["returns"].rolling(20).std()
        out["atr"] = (out["high"] - out["low"]).rolling(14).mean()
        out["trend"] = np.where(out["close"] > out["close"].rolling(50).mean(), 1, -1)
        out["volume_z"] = (out["volume"] - out["volume"].rolling(30).mean()) / (
            out["volume"].rolling(30).std() + 1e-9
        )

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
        if prepared.empty or len(prepared) < LABEL_MAX_BARS + 20:
            return pd.DataFrame()

        labels = label_tp_before_sl(
            prepared["high"].values,
            prepared["low"].values,
            prepared["close"].values,
            prepared["atr"].values,
            max_bars=LABEL_MAX_BARS,
            sl_atr_mult=LABEL_SL_ATR_MULT,
            rr_ratio=LABEL_RR_RATIO,
        )
        prepared["target"] = labels
        prepared = prepared.dropna(subset=["target"])
        prepared["target"] = prepared["target"].astype(int)
        return prepared.dropna(subset=self.feature_columns)

    def prepare_inference_features(self, df):
        prepared = self._compute_base_features(df)
        if prepared.empty:
            return pd.DataFrame()
        return prepared.dropna(subset=self.feature_columns)

    def fit_from_dataframe(self, df, save=False):
        """Train on historical bars only (no future rows in the slice)."""
        prepared = self.prepare_training_features(df)
        if len(prepared) < self.min_train_samples:
            logging.debug(
                "JARVIS | Skip train: only %s labeled samples.", len(prepared)
            )
            return False

        X_raw = prepared[self.feature_columns]
        y = prepared["target"]
        self.scaler.fit(X_raw)
        self.scaler_fitted = True
        X = self.scaler.transform(X_raw)
        self.model.fit(X, y)
        self.is_trained = True
        self.last_train_len = len(df)
        logging.info(
            "JARVIS | Trained on %s samples (long-win rate %.1f%%).",
            len(prepared),
            100.0 * y.mean(),
        )
        if save and self.model_path:
            self.save_brain()
        return True

    def continuous_learn(self, df, force=False):
        """Retrain on a rolling window when enough new bars arrive."""
        if df is None or len(df) < self.min_train_samples + LABEL_MAX_BARS:
            return False

        if not force and self.last_train_len is not None:
            if len(df) - self.last_train_len < self.retrain_bar_gap:
                return False

        # Exclude the latest bars so labels do not peek at the open candle.
        train_df = df.iloc[: -LABEL_MAX_BARS] if len(df) > 800 else df.iloc[:-LABEL_MAX_BARS]
        if len(train_df) > 800:
            train_df = train_df.iloc[-800:]
        return self.fit_from_dataframe(train_df, save=False)

    def signal(self, df):
        if not self.is_trained or not self.scaler_fitted:
            return "HOLD"

        prepared = self.prepare_inference_features(df)
        if prepared.empty:
            return "HOLD"

        X = self.scaler.transform(prepared[self.feature_columns].iloc[-1:])
        prob = self.model.predict_proba(X)[0][1]

        if prob > 0.58:
            return "BUY"
        if prob < 0.42:
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
        if df is not None and len(df) > self.min_train_samples:
            self.continuous_learn(df, force=(pnl is not None and pnl < 0))

    def save_brain(self):
        if not self.model_path:
            return
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "scaler_fitted": self.scaler_fitted,
                "last_train_len": self.last_train_len,
            },
            self.model_path,
        )
