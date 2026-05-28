# strategy.py
import numpy as np
import pandas as pd
import ta


# ─────────────────────────────────────────────────────────────────────────────
def _supertrend(df, period=10, multiplier=2.5):
    """
    Supertrend baseado em ATR.
    direction: 1.0 = bullish  |  -1.0 = bearish
    line:      suporte/resistência
    """
    high  = df['high'].values.astype(float)
    low   = df['low'].values.astype(float)
    close = df['close'].values.astype(float)
    n     = len(df)

    atr_vals = ta.volatility.AverageTrueRange(
        high=df['high'], low=df['low'], close=df['close'], window=period
    ).average_true_range().values

    hl2         = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr_vals
    basic_lower = hl2 - multiplier * atr_vals

    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    direction   = np.full(n, np.nan)
    line        = np.full(n, np.nan)

    for i in range(period, n):
        if np.isnan(final_upper[i - 1]):
            final_upper[i] = basic_upper[i]
        elif basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        if np.isnan(final_lower[i - 1]):
            final_lower[i] = basic_lower[i]
        elif basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        if np.isnan(direction[i - 1]):
            direction[i] = 1.0
        elif direction[i - 1] == -1 and close[i] > final_upper[i]:
            direction[i] = 1.0
        elif direction[i - 1] == 1 and close[i] < final_lower[i]:
            direction[i] = -1.0
        else:
            direction[i] = direction[i - 1]

        line[i] = final_lower[i] if direction[i] == 1 else final_upper[i]

    return pd.Series(direction, index=df.index), pd.Series(line, index=df.index)


# ─────────────────────────────────────────────────────────────────────────────
def apply_indicators(df):
    """
    Indicadores implementados a partir do Pine Script WDO Master V3:

    Welles Wilder (Pine Script): ta.ema(close, period * 2 - 1)
      Período 3  → EMA(5)
      Período 8  → EMA(15)
      Período 20 → EMA(39)

    Didi Index:
      linha3  = 100 * (m3  - m8) / m8   ← curta (azul)
      linha20 = 100 * (m20 - m8) / m8   ← longa (amarela)

    Sinal:
      compraSinal = crossover(linha3, linha20) AND linha3 > 0
      vendaSinal  = crossunder(linha3, linha20) AND linha3 < 0

    Overlays (do force_overlay do script):
      EMA 50   → MME 50    (laranja)
      SMA 200  → MMS 200   (branco)
      VWAP     → diário    (magenta)
    """
    for col in ('close', 'open', 'high', 'low', 'volume'):
        df[col] = df[col].astype(float)

    # ── Supertrend (ATR 10, multiplicador 2.5) ──────────────────────────────
    df['st_dir'], df['st_line'] = _supertrend(df, period=10, multiplier=2.5)

    # ── EMA 50 e SMA 200 (do Pine Script: MME 50 e MMS 200) ────────────────
    df['ema50']  = ta.trend.ema_indicator(df['close'], window=50)
    df['sma200'] = df['close'].rolling(200).mean()

    # ── Didi Index — Welles Wilder (ta.ema(close, period*2-1)) ─────────────
    m3  = ta.trend.ema_indicator(df['close'], window=3  * 2 - 1)   # EMA(5)
    m8  = ta.trend.ema_indicator(df['close'], window=8  * 2 - 1)   # EMA(15)
    m20 = ta.trend.ema_indicator(df['close'], window=20 * 2 - 1)   # EMA(39)

    df['didi_short'] = 100.0 * (m3  - m8) / m8   # linha3  (curta, azul)
    df['didi_long']  = 100.0 * (m20 - m8) / m8   # linha20 (longa, amarela)

    # ── Crossovers do Didi (conforme Pine Script) ───────────────────────────
    # compraSinal = ta.crossover(linha3, linha20) AND linha3 > 0
    # vendaSinal  = ta.crossunder(linha3, linha20) AND linha3 < 0
    ds_arr = df['didi_short'].values
    dl_arr = df['didi_long'].values
    signals = np.zeros(len(df))
    for i in range(1, len(df)):
        if np.isnan(ds_arr[i]) or np.isnan(dl_arr[i]):
            continue
        if np.isnan(ds_arr[i - 1]) or np.isnan(dl_arr[i - 1]):
            continue
        # Agulhada de compra
        if ds_arr[i - 1] <= dl_arr[i - 1] and ds_arr[i] > dl_arr[i] and ds_arr[i] > 0:
            signals[i] = 1.0
        # Agulhada de venda
        elif ds_arr[i - 1] >= dl_arr[i - 1] and ds_arr[i] < dl_arr[i] and ds_arr[i] < 0:
            signals[i] = -1.0
    df['didi_signal'] = signals

    # ── VWAP diário (reseta à meia-noite UTC, como no Pine Script) ──────────
    df['_tp']  = (df['high'] + df['low'] + df['close']) / 3.0
    df['_tpv'] = df['_tp'] * df['volume']
    df['_dt']  = pd.to_datetime(df['time'], unit='ms').dt.normalize()

    vwap_vals = np.full(len(df), np.nan)
    for _, grp in df.groupby('_dt', sort=False):
        idx = grp.index.tolist()
        cum_tpv = grp['_tpv'].cumsum().values
        cum_vol = grp['volume'].cumsum().values
        with np.errstate(divide='ignore', invalid='ignore'):
            v = np.where(cum_vol > 0, cum_tpv / cum_vol, np.nan)
        for k, pos in enumerate(idx):
            vwap_vals[pos] = v[k]

    df['vwap'] = vwap_vals
    df.drop(columns=['_tp', '_tpv', '_dt'], inplace=True)

    # ── Volume médio 20 candles ───────────────────────────────────────────
    df['vol_mean'] = df['volume'].rolling(20).mean()

    return df


# ─────────────────────────────────────────────────────────────────────────────
def generate_signal(df):
    """
    Estratégia: Supertrend + EMA50 + Didi Agulhada (Welles Wilder) + Volume
    ────────────────────────────────────────────────────────────────────────
    COMPRA — todas as 4 condições:
      1. Supertrend BULLISH              → ATR(10) × 2.5
      2. Preço acima da EMA50            → tendência de médio prazo
      3. Didi "agulhada de compra":
           linha3 > linha20  E  linha3 > 0   (estado pós-crossover de compra)
      4. Volume ≥ 1.2× média 20 candles  → confirmação de força

    VENDA — qualquer condição:
      1. Supertrend vira BEARISH         → principal gatilho
      2. Didi "agulhada de venda":
           linha3 < linha20  E  linha3 < 0   (estado pós-crossover de venda)
    """
    if len(df) < 50:
        return "hold"

    last = df.iloc[-1]

    for col in ['st_dir', 'ema50', 'didi_short', 'didi_long']:
        if pd.isna(last[col]):
            return "hold"

    st_bull  = float(last['st_dir'])    == 1.0
    ema_bull = float(last['close'])      > float(last['ema50'])
    ds       = float(last['didi_short'])
    dl       = float(last['didi_long'])

    didi_buy  = ds > dl and ds > 0    # estado de agulhada de compra ativa
    didi_sell = ds < dl and ds < 0    # estado de agulhada de venda ativa

    vol_mean = float(last['vol_mean']) if not pd.isna(last['vol_mean']) else 0
    vol_ok   = float(last['volume']) >= vol_mean * 1.2 if vol_mean > 0 else True

    # ── COMPRA ────────────────────────────────────────────────────────────
    if st_bull and ema_bull and didi_buy and vol_ok:
        return "buy"

    # ── VENDA ─────────────────────────────────────────────────────────────
    if not st_bull or didi_sell:
        return "sell"

    return "hold"
