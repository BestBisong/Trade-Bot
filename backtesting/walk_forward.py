import datetime
import json
import os

from strategies.execution_levels import stop_distance
from strategies.regime import detect_market_regime, get_regime_params
from execution.sizing import apply_slippage, settlement_pnl


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


def _simulate_window(test_slice, trend_df, model, tuned_params, initial_balance, taker_fee_rate):
    """Mini backtest with TP/SL exits aligned to live bot."""
    equity = initial_balance
    equity_curve = [equity]
    trades = 0
    wins = 0
    open_trade = None
    last_close_i = -50

    for i in range(60, len(test_slice) - 3):
        sub = test_slice.iloc[: i + 1]
        price = float(sub["close"].iloc[-1])
        trend_sub = trend_df.loc[trend_df.index <= sub.index[-1]].tail(150)
        if trend_sub.empty:
            continue

        if open_trade:
            hit_tp = (open_trade["side"] == "buy" and price >= open_trade["tp"]) or (
                open_trade["side"] == "sell" and price <= open_trade["tp"]
            )
            hit_sl = (open_trade["side"] == "buy" and price <= open_trade["sl"]) or (
                open_trade["side"] == "sell" and price >= open_trade["sl"]
            )
            if hit_tp or hit_sl:
                exit_fill = apply_slippage(price, open_trade["side"], 5)
                pnl = settlement_pnl(
                    open_trade["entry"],
                    exit_fill,
                    open_trade["qty"],
                    open_trade["side"],
                    taker_fee_rate,
                )
                equity += pnl
                equity_curve.append(equity)
                trades += 1
                if pnl > 0:
                    wins += 1
                open_trade = None
                last_close_i = i
            continue

        if i - last_close_i < 12:
            continue

        from signals.signal_generator import generate

        signal, _, _ = generate(sub, trend_sub, model, tuned_params=tuned_params)
        if signal not in ["BUY", "SELL"]:
            continue

        regime = detect_market_regime(sub, trend_sub)
        params = get_regime_params(regime)
        sl_dist = stop_distance(sub, regime, tuned_params)
        if sl_dist <= 0:
            continue

        entry = apply_slippage(price, signal.lower(), 5)
        qty = (equity * 0.01) / sl_dist
        qty = min(qty, (equity * 0.25) / entry)
        if qty <= 0 or qty * entry < 5:
            continue

        sl = entry - sl_dist if signal == "BUY" else entry + sl_dist
        tp = entry + sl_dist * params["rr_ratio"] if signal == "BUY" else entry - sl_dist * params["rr_ratio"]
        open_trade = {"side": signal.lower(), "entry": entry, "sl": sl, "tp": tp, "qty": qty}

    return equity, equity_curve, trades, wins


def run_walk_forward_validation(
    symbols,
    timeframe,
    trend_timeframe,
    initial_balance=1000.0,
    train_bars=240,
    test_bars=120,
    step_bars=120,
    taker_fee_rate=0.0006,
    tuned_params=None,
):
    from backtesting.historical_data import fetch_historical
    from strategies.ml_strategy import MLStrategy
    from backtesting.self_tuner import load_tuned_params

    if tuned_params is None:
        tuned_params = load_tuned_params()["params"]

    report = {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
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

            model = MLStrategy(model_path=None, load_pretrained=False)
            model.fit_from_dataframe(train_slice)

            equity, equity_curve, trades, wins = _simulate_window(
                test_slice,
                trend_df,
                model,
                tuned_params,
                initial_balance,
                taker_fee_rate,
            )

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
