def win_rate(trades):
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t[0] == "BUY")
    return wins / len(trades)