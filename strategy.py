# strategy.py
import numpy as np
import pandas as pd
import ta
import config


# ─────────────────────────────────────────────────────────────────────────────
def apply_indicators(df):
    """
    Estratégia Híbrida Profissional: 
    1. Keltner Channels (Encontrar preço barato/pullback)
    2. Didi Index (Confirmar início de explosão - Agulhada)
    3. SMA 200 (Garantir que estamos na tendência de alta)
    """
    for col in ('close', 'open', 'high', 'low', 'volume'):
        df[col] = df[col].astype(float)

    # ── SMA 200 (Filtro de Tendência Macro - Longo Prazo) ───────────────────
    df['sma200'] = df['close'].rolling(200).mean()
    
    # ── EMA 20 (Coração do Canal de Keltner) ────────────────────────────────
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
    
    # ── ATR (14 períodos) - Mede o "tamanho" da volatilidade ───────────────
    df['tr'] = np.maximum(df['high'] - df['low'],
               np.maximum(abs(df['high'] - df['close'].shift()),
                          abs(df['low'] - df['close'].shift())))
    df['atr'] = df['tr'].rolling(14).mean()
    
    # ── Bandas de Keltner (Onde o preço costuma "bater e voltar") ──────────
    df['kc_upper'] = df['ema20'] + (2.0 * df['atr'])
    df['kc_lower'] = df['ema20'] - (2.0 * df['atr'])

    # ── Didi Index (A famosa 'Agulhada') ────────────────────────────────────
    # m3 (curta), m8 (referência), m20 (longa)
    m3  = ta.trend.ema_indicator(df['close'], window=3 * 2 - 1)
    m8  = ta.trend.ema_indicator(df['close'], window=8 * 2 - 1)
    m20 = ta.trend.ema_indicator(df['close'], window=20 * 2 - 1)

    df['didi_short'] = 100.0 * (m3 - m8) / m8
    df['didi_long']  = 100.0 * (m20 - m8) / m8

    # ── RSI(14) — Mede se o mercado está "cansado" ou com força ─────────────
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    
    # ── ADX — Mede a força da tendência atual ───────────────────────────────
    df['adx'] = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()

    # ── Volume Médio (20 períodos) ──────────────────────────────────────────
    df['vol_mean'] = df['volume'].rolling(20).mean()

    return df


# ─────────────────────────────────────────────────────────────────────────────
def generate_signal(df):
    """
    Sinal Sniper Pullback + Didi Agulhada
    
    COMPRA:
      1. Preço > SMA 200 (Mercado em alta no longo prazo)
      2. Preço < EMA 20 (Bitcoin deu um desconto/pullback)
      3. Didi Short > Didi Long (Agulhada de compra começando)
      4. RSI > 45 (Mostrando que a queda parou e está voltando a subir)
    """
    if len(df) < 201:
        return "hold"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Validação de dados básicos
    for col in ['sma200', 'ema20', 'didi_short', 'didi_long', 'rsi']:
        if pd.isna(last[col]):
            return "hold"

    # 1. Filtro Macro: Só compramos se o mercado estiver saudável (acima da média 200)
    macro_bull = last['close'] > last['sma200']
    
    # 2. Pullback: Esperamos o preço cair um pouco (tocar/ficar abaixo da média 20)
    # Isso evita comprar no topo da montanha.
    is_pullback = last['low'] < last['ema20']
    
    # 3. Agulhada Didi: Linha curta cruzando a longa para cima
    didi_buy = last['didi_short'] > last['didi_long']
    
    # 4. Força de Reação: RSI precisa estar subindo e acima de 45
    rsi_rising = last['rsi'] > prev['rsi'] and last['rsi'] > 45.0
    
    # 5. Volume: Precisa ter gente negociando
    vol_ok = last['volume'] > last['vol_mean']

    # ── DECISÃO DE COMPRA ───────────────────────────────────────────────
    if macro_bull and is_pullback and didi_buy and rsi_rising and vol_ok:
        return "buy"

    # ── DECISÃO DE VENDA ────────────────────────────────────────────────
    # Vende se o preço esticar demais (tocar banda superior de Keltner)
    # Ou se o RSI ficar muito alto (exaustão), ou se a tendência macro virar.
    if last['high'] > last['kc_upper'] or last['rsi'] > 78 or last['close'] < last['sma200']:
        return "sell"

    return "hold"
