def win_rate(trades):
    wins = sum(1 for t in trades if t[0] == "BUY")
    return wins / len(trades)