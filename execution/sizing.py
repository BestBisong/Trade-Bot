from decimal import Decimal, ROUND_DOWN


def apply_exchange_constraints(raw_qty, min_qty, qty_precision, min_notional, price):
    """Quantize and validate order quantity against exchange rules."""
    if raw_qty is None or price is None or price <= 0:
        return 0.0

    quant = Decimal("1").scaleb(-int(qty_precision))
    qty = Decimal(str(max(raw_qty, 0.0))).quantize(quant, rounding=ROUND_DOWN)

    if qty < Decimal(str(min_qty)):
        return 0.0

    notional = qty * Decimal(str(price))
    if notional < Decimal(str(min_notional)):
        return 0.0

    return float(qty)


def calculate_order_quantity(
    wallet,
    entry_price,
    stop_distance,
    risk_per_trade=0.01,
    max_notional_fraction=0.25,
    min_qty=0.0,
    qty_precision=6,
    min_notional=0.0,
):
    """Calculate position size from risk model, then enforce exchange constraints."""
    if wallet <= 0 or entry_price <= 0 or stop_distance <= 0:
        return 0.0

    risk_budget = wallet * risk_per_trade
    qty_by_risk = risk_budget / stop_distance
    qty_by_notional = (wallet * max_notional_fraction) / entry_price
    raw_qty = min(qty_by_risk, qty_by_notional)

    return apply_exchange_constraints(
        raw_qty=raw_qty,
        min_qty=min_qty,
        qty_precision=qty_precision,
        min_notional=min_notional,
        price=entry_price,
    )


def apply_slippage(price, side, slippage_bps=5):
    """Apply deterministic slippage model in basis points (1 bps = 0.01%)."""
    slip = max(slippage_bps, 0) / 10000.0
    if side.lower() == "buy":
        return price * (1 + slip)
    return price * (1 - slip)


def settlement_pnl(entry_price, exit_price, qty, side, taker_fee_rate=0.0006):
    """Return net PnL after fees for a completed trade."""
    if qty <= 0 or entry_price <= 0 or exit_price <= 0:
        return 0.0

    gross = (exit_price - entry_price) * qty if side == "buy" else (entry_price - exit_price) * qty
    fees = (entry_price + exit_price) * qty * taker_fee_rate
    return gross - fees
