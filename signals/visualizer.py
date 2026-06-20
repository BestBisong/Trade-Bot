import pandas as pd
import os

try:
    import mplfinance as mpf
    has_mpl = True
except ImportError:
    has_mpl = False

def visualize_trade(df, symbol, signal, price, strategy_name):
    """
    Generates a chart showing the trade entry and target levels.
    """
    if not has_mpl:
        return ""
    plot_df = df.tail(30).copy()
    plot_df.index = pd.to_datetime(plot_df.index)
    
    tp_level = price * 1.01 if signal == "BUY" else price * 0.99
    sl_level = price * 0.995 if signal == "BUY" else price * 1.005
    
    hlines = dict(hlines=[tp_level, sl_level, price],
                  colors=['blue', 'red', 'gray'], 
                  linestyle='-.', linewidths=1)

    os.makedirs('plots', exist_ok=True)
    
    
    clean_symbol = symbol.replace("/", "_") 
    filename = f"plots/{clean_symbol}_{signal}_{pd.Timestamp.now().strftime('%H%M%S')}.png"
    
    mpf.plot(plot_df, type='candle', style='charles',
             title=f"{symbol} {signal} - {strategy_name}",
             hlines=hlines, savefig=filename)
    
    return filename