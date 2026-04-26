from execution.sizing import (
    calculate_order_quantity,
    apply_exchange_constraints,
    settlement_pnl,
)


def test_apply_exchange_constraints_rejects_below_min_notional():
    qty = apply_exchange_constraints(
        raw_qty=0.0002,
        min_qty=0.0001,
        qty_precision=4,
        min_notional=10.0,
        price=20000.0,
    )
    assert qty == 0.0


def test_calculate_order_quantity_honors_precision_and_min_qty():
    qty = calculate_order_quantity(
        wallet=1000.0,
        entry_price=20000.0,
        stop_distance=50.0,
        risk_per_trade=0.01,
        max_notional_fraction=0.30,
        min_qty=0.0001,
        qty_precision=4,
        min_notional=5.0,
    )
    # Risk gives 0.2, notional cap gives 0.015. With 4dp rounding => 0.0150.
    assert qty == 0.015


def test_settlement_pnl_buy_net_of_fees():
    pnl = settlement_pnl(
        entry_price=100.0,
        exit_price=101.0,
        qty=10.0,
        side="buy",
        taker_fee_rate=0.001,
    )
    # Gross = +10. Fees=(100+101)*10*0.001=2.01 => Net=7.99
    assert round(pnl, 2) == 7.99


def test_settlement_pnl_sell_net_of_fees():
    pnl = settlement_pnl(
        entry_price=100.0,
        exit_price=98.0,
        qty=5.0,
        side="sell",
        taker_fee_rate=0.001,
    )
    # Gross = +10. Fees=(100+98)*5*0.001=0.99 => Net=9.01
    assert round(pnl, 2) == 9.01