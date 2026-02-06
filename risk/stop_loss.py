def stop_loss(entry_price, percent=2):
    return entry_price * (1 - percent / 100)