import numpy as np


def compute_metrics(trades: list, initial_capital: float = 100.0) -> dict:
    """
    Computes a full institutional-grade performance report from a list of closed trades.
    Each trade must have: { 'pnl', 'side', 'entry', 'exit', 'symbol', 'regime' }
    """
    if not trades:
        return {"error": "No trades to analyse."}

    pnls = [t["pnl"] for t in trades]
    equity_curve = [initial_capital]
    for p in pnls:
        equity_curve.append(equity_curve[-1] + p)

    final_equity = equity_curve[-1]
    total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

    # Max Drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Sharpe Ratio (annualised based on actual trade frequency per year)
    returns = np.diff(equity_curve) / equity_curve[:-1]
    
    # We estimate trades per year based on the 180-day lookback period
    lookback_days = 180
    trades_per_year = (len(pnls) / lookback_days) * 365.25 if len(pnls) > 0 else 0
    
    sharpe = 0.0
    if returns.std() > 0 and trades_per_year > 0:
        sharpe = (returns.mean() / returns.std()) * np.sqrt(trades_per_year)


    # Expectancy: average $ you make/lose per trade
    expectancy = np.mean(pnls) if pnls else 0

    # Consecutive losses
    max_consec_losses = 0
    cur = 0
    for p in pnls:
        if p <= 0:
            cur += 1
            max_consec_losses = max(max_consec_losses, cur)
        else:
            cur = 0

    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "avg_win_usd": round(avg_win, 4),
        "avg_loss_usd": round(avg_loss, 4),
        "profit_factor": round(profit_factor, 3),
        "risk_reward_ratio": round(rr_ratio, 3),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "total_return_pct": round(total_return_pct, 2),
        "final_equity_usd": round(final_equity, 2),
        "expectancy_per_trade_usd": round(expectancy, 4),
        "max_consecutive_losses": max_consec_losses,
        "equity_curve": equity_curve,
    }