# strategy.py
import numpy as np
import pandas as pd
import ta


# ─────────────────────────────────────────────────────────────────────────────
def _supertrend(df, period=10, multiplier=2.5):
    """Supertrend baseado em ATR. direction: 1.0=bullish | -1.0=bearish"""
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
    Indicadores baseados no Pine Script WDO Master V3 + RSI(14).

    Didi Index (Welles Wilder — ta.ema equivalente: period*2-1):
      m3  = EMA(5)  → linha curta  (azul)
      m8  = EMA(15) → referência
      m20 = EMA(39) → linha longa  (amarela)
      linha3  = 100*(m3  - m8)/m8
      linha20 = 100*(m20 - m8)/m8
    """
    for col in ('close', 'open', 'high', 'low', 'volume'):
        df[col] = df[col].astype(float)

    # ── Supertrend (ATR 10, multiplicador 2.5) ──────────────────────────────
    df['st_dir'], df['st_line'] = _supertrend(df, period=10, multiplier=2.5)

    # ── EMA 50 e SMA 200 ────────────────────────────────────────────────────
    df['ema50']  = ta.trend.ema_indicator(df['close'], window=50)
    df['sma200'] = df['close'].rolling(200).mean()

    # ── RSI(14) — filtro de sobrecompra/sobrevenda ──────────────────────────
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

    # ── Didi Index — Welles Wilder ──────────────────────────────────────────
    m3  = ta.trend.ema_indicator(df['close'], window=3  * 2 - 1)
    m8  = ta.trend.ema_indicator(df['close'], window=8  * 2 - 1)
    m20 = ta.trend.ema_indicator(df['close'], window=20 * 2 - 1)

    df['didi_short'] = 100.0 * (m3  - m8) / m8
    df['didi_long']  = 100.0 * (m20 - m8) / m8

    # ── Crossovers do Didi ──────────────────────────────────────────────────
    ds_arr = df['didi_short'].values
    dl_arr = df['didi_long'].values
    signals = np.zeros(len(df))
    for i in range(1, len(df)):
        if np.isnan(ds_arr[i]) or np.isnan(dl_arr[i]):
            continue
        if np.isnan(ds_arr[i - 1]) or np.isnan(dl_arr[i - 1]):
            continue
        if ds_arr[i - 1] <= dl_arr[i - 1] and ds_arr[i] > dl_arr[i] and ds_arr[i] > 0:
            signals[i] = 1.0
        elif ds_arr[i - 1] >= dl_arr[i - 1] and ds_arr[i] < dl_arr[i] and ds_arr[i] < 0:
            signals[i] = -1.0
    df['didi_signal'] = signals

    # ── VWAP diário (reseta à meia-noite UTC) ───────────────────────────────
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

    # ── Volume médio 20 candles ─────────────────────────────────────────────
    df['vol_mean'] = df['volume'].rolling(20).mean()

    return df


# ─────────────────────────────────────────────────────────────────────────────
def generate_signal(df):
    """
    Estratégia: Supertrend + EMA50 + Didi Agulhada + Volume + RSI
    ─────────────────────────────────────────────────────────────────────────
    COMPRA — 5 condições (todas obrigatórias):
      1. Supertrend BULLISH              → ATR(10) × 2.5
      2. Preço > EMA50                   → tendência de médio prazo
      3. Didi agulhada de compra ativa   → L3 > L20 e L3 > 0
      4. Volume >= 1.2× média 20         → confirmação de força
      5. RSI(14) < 70                    → não sobrecomprado

    VENDA — requer 2 confirmações (evita saídas prematuras por ruído):
      Principal: Supertrend BEARISH + (Didi venda OU Preço < EMA50)
      Alternativa: RSI(14) > 80          → sobrecompra extrema, realizar

    Correção vs versão anterior:
      Antes: `if not st_bull OR didi_sell` → saía na primeira vela bearish
      Agora: exige 2 condições simultâneas → mais robusto contra ruído do ST
    """
    if len(df) < 50:
        return "hold"

    last = df.iloc[-1]

    for col in ['st_dir', 'ema50', 'didi_short', 'didi_long', 'rsi']:
        if pd.isna(last[col]):
            return "hold"

    st_bull  = float(last['st_dir']) == 1.0
    ema_bull = float(last['close']) > float(last['ema50'])
    ds       = float(last['didi_short'])
    dl       = float(last['didi_long'])
    rsi      = float(last['rsi'])

    didi_buy  = ds > dl and ds > 0
    didi_sell = ds < dl and ds < 0

    vol_mean = float(last['vol_mean']) if not pd.isna(last['vol_mean']) else 0
    vol_ok   = float(last['volume']) >= vol_mean * 1.2 if vol_mean > 0 else True

    # ── COMPRA (5 filtros) ────────────────────────────────────────────────
    if st_bull and ema_bull and didi_buy and vol_ok and rsi < 70:
        return "buy"

    # ── VENDA (2 confirmações necessárias) ────────────────────────────────
    st_bear = not st_bull
    if (st_bear and didi_sell) or (st_bear and not ema_bull) or rsi > 80:
        return "sell"

    return "hold"
