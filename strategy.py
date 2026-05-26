# strategy.py
import pandas as pd
import ta

def apply_indicators(df):
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)

    # 1. RSI de 14 períodos
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()

    # 2. Média Móvel Simples de 50 períodos (SMA50)
    df['sma50'] = ta.trend.sma_indicator(close=df['close'], window=50)

    # 3. Média de Volume dos últimos 20 candles
    df['vol_mean'] = df['volume'].rolling(20).mean()

    return df

def generate_signal(df):
    if len(df) < 51:
        return "hold"
        
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.isna(last['rsi']) or pd.isna(last['sma50']) or pd.isna(last['vol_mean']):
        return "hold"

    # Tendência de Alta: Preço acima da SMA50 E a SMA50 subindo
    tendencia_alta = (last['close'] > last['sma50']) and (last['sma50'] > prev['sma50'])

    if tendencia_alta and (last['rsi'] < 40) and (last['volume'] > last['vol_mean']):
        return "buy"
    elif last['rsi'] > 65:
        return "sell"

    return "hold"