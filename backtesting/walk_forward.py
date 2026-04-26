import datetime
import json
import os


def _safe_write_json(path, payload):
    with open(path, "w") as f:
        json.dump(payload, f, default=str)


def _equity_curve_metrics(equity_curve):
    if not equity_curve:
        return {"max_drawdown_pct": 0.0}

    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        peak = max(peak, val)
        dd = (val - peak) / peak if peak > 0 else 0.0
        max_dd = min(max_dd, dd)
    return {"max_drawdown_pct": abs(max_dd) * 100.0}


def run_walk_forward_validation(
    symbols,
    timeframe,
    trend_timeframe,
    initial_balance=1000.0,
    train_bars=240,
    test_bars=120,
    step_bars=120,
    taker_fee_rate=0.0006,
):
    """Evaluate strategy with rolling train/test windows and return aggregate metrics."""
    from backtesting.historical_data import fetch_historical
    from signals.signal_generator import generate
    from strategies.ml_strategy import MLStrategy

    report = {
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "symbols": symbols,
        "windows": [],
        "aggregate": {},
    }

    all_pnls = []
    total_trades = 0
    total_wins = 0
    all_drawdowns = []

    for symbol in symbols:
        df = fetch_historical(symbol=symbol, timeframe=timeframe, limit=900)
        trend_df = fetch_historical(symbol=symbol, timeframe=trend_timeframe, limit=900)

        if df is None or trend_df is None or len(df) < (train_bars + test_bars + 20):
            continue

        start = train_bars
        while start + test_bars <= len(df):
            train_slice = df.iloc[start - train_bars : start]
            test_slice = df.iloc[start : start + test_bars]

            model = MLStrategy(model_path=f"tmp_walkforward_{symbol.replace('/', '_')}.joblib")
            model.continuous_learn(train_slice)

            equity = initial_balance
            equity_curve = [equity]
            trades = 0
            wins = 0

            for i in range(60, len(test_slice) - 3):
                sub = test_slice.iloc[: i + 1]
                trend_sub = trend_df.loc[trend_df.index <= sub.index[-1]].tail(150)
                if trend_sub is None or trend_sub.empty:
                    continue

                signal, _, _ = generate(sub, trend_sub, model)
                if signal not in ["BUY", "SELL"]:
                    continue

                entry = float(sub["close"].iloc[-1])
                exit_price = float(sub["close"].shift(-3).iloc[-1])
                if entry <= 0 or exit_price <= 0:
                    continue

                qty = (equity * 0.01) / max(abs(entry * 0.002), 1e-9)
                gross = (exit_price - entry) * qty if signal == "BUY" else (entry - exit_price) * qty
                fees = (entry + exit_price) * qty * taker_fee_rate
                pnl = gross - fees

                trades += 1
                if pnl > 0:
                    wins += 1
                equity += pnl
                equity_curve.append(equity)

            metrics = _equity_curve_metrics(equity_curve)
            window_report = {
                "symbol": symbol,
                "train_start": str(train_slice.index[0]),
                "train_end": str(train_slice.index[-1]),
                "test_start": str(test_slice.index[0]),
                "test_end": str(test_slice.index[-1]),
                "trades": trades,
                "wins": wins,
                "win_rate": (wins / trades * 100.0) if trades else 0.0,
                "net_pnl": equity - initial_balance,
                "max_drawdown_pct": metrics["max_drawdown_pct"],
            }
            report["windows"].append(window_report)

            all_pnls.append(window_report["net_pnl"])
            total_trades += trades
            total_wins += wins
            all_drawdowns.append(window_report["max_drawdown_pct"])

            start += step_bars

    report["aggregate"] = {
        "total_windows": len(report["windows"]),
        "total_trades": total_trades,
        "win_rate": (total_wins / total_trades * 100.0) if total_trades else 0.0,
        "avg_window_pnl": (sum(all_pnls) / len(all_pnls)) if all_pnls else 0.0,
        "worst_drawdown_pct": max(all_drawdowns) if all_drawdowns else 0.0,
    }

    _safe_write_json("walk_forward_report.json", report)
    return report


def live_gate_from_walk_forward(report, min_win_rate=52.0, min_windows=3, max_drawdown_pct=12.0):
    """Return whether walk-forward stats are good enough for live capital."""
    agg = report.get("aggregate", {})
    total_windows = int(agg.get("total_windows", 0))
    win_rate = float(agg.get("win_rate", 0.0))
    worst_dd = float(agg.get("worst_drawdown_pct", 100.0))

    allowed = (
        total_windows >= min_windows
        and win_rate >= min_win_rate
        and worst_dd <= max_drawdown_pct
    )

    return {
        "allowed": allowed,
        "criteria": {
            "min_win_rate": min_win_rate,
            "min_windows": min_windows,
            "max_drawdown_pct": max_drawdown_pct,
        },
        "measured": {
            "win_rate": win_rate,
            "total_windows": total_windows,
            "worst_drawdown_pct": worst_dd,
        },
    }


def should_refresh_walk_forward(report_path="walk_forward_report.json", max_age_hours=24):
    if not os.path.exists(report_path):
        return True

    modified = datetime.datetime.fromtimestamp(os.path.getmtime(report_path))
    age = datetime.datetime.now() - modified
    return age.total_seconds() > (max_age_hours * 3600)
