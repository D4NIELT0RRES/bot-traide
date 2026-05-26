import ta
import pandas as pd

def apply_indicators(df):
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)

    rsi = ta.momentum.RSIIndicator(close=df['close'], window=14)
    df['rsi'] = rsi.rsi()

    sma = ta.trend.SMAIndicator(close=df['close'], window=50)
    df['sma50'] = sma.sma_indicator()

    df['vol_mean'] = df['volume'].rolling(20).mean()

    return df


def generate_signal(df):
    last = df.iloc[-1]

    price = last['close']
    rsi = last['rsi']
    sma50 = last['sma50']
    volume = last['volume']
    vol_mean = last['vol_mean']

    if pd.isna(rsi) or pd.isna(sma50) or pd.isna(vol_mean):
        return "hold"

    tendencia_alta = (
        price > sma50 and
        df['sma50'].iloc[-1] > df['sma50'].iloc[-2]
    )

    if (
        tendencia_alta and
        rsi < 40 and
        volume > vol_mean
    ):
        return "buy"

    elif rsi > 65:
        return "sell"

    return "hold"