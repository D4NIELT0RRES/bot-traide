import pandas as pd
import ta

def smma(series, period):
    """Calcula a Média Móvel Suavizada (Welles Wilder)."""
    return series.ewm(alpha=1/period, adjust=False).mean()

def apply_indicators(df):
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)

    # Médias de Welles Wilder (SMMA)
    df['smma3'] = smma(df['close'], 3)
    df['smma8'] = smma(df['close'], 8)
    df['smma20'] = smma(df['close'], 20)
    
    # RSI para filtro de força
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    
    return df

def generate_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Lógica Didi Index: Compra no cruzamento da média 3 sobre a 8, ancorada pela 20
    didi_buy = (prev['smma3'] < prev['smma8']) and \
               (last['smma3'] > last['smma8']) and \
               (last['smma3'] > last['smma20'])
    
    # Venda: Cruzamento para baixo ou RSI sobrecomprado
    didi_sell = (prev['smma3'] > prev['smma8']) and (last['smma3'] < last['smma8'])
    
    if didi_buy and last['rsi'] < 50:
        return "buy"
    elif didi_sell or last['rsi'] > 65:
        return "sell"
    
    return "hold"