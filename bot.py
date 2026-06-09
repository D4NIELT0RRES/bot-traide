# bot.py
import ccxt
import pandas as pd
import time
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import config

load_dotenv()

import requests
from config import (
    API_KEY, SECRET, SYMBOL, TIMEFRAME,
    STOP_LOSS, TRAILING_PCT, TAKE_PROFIT, TRADE_SIZE_PCT,
    COOLDOWN_BARS, MIN_HOLD_BARS, STATE_FILE, CONTROL_FILE,
    RISK_PER_TRADE_PCT, ATR_STOP_MULT, ATR_TRAILING_MULT,
    FEES_PCT, SLIPPAGE_PCT, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
)
from strategy import apply_indicators, generate_signal

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

_start_time = int(time.time())


# ── Notificações ─────────────────────────────────────────────────────────────
def notify(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    full_msg = f"🤖 [BOT BTC] {msg}"
    print(f"[{ts}] {full_msg}")
    
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": full_msg}, timeout=5)
        except Exception as e:
            print(f"Erro Telegram: {e}")


# ── Estado ────────────────────────────────────────────────────────────────────
def load_state():
    defaults = {
        "position": None,
        "partial_taken": False,
        "entry_price": 0.0,
        "last_candle_time": 0,
        "last_trade_candle": 0,
        "trade_log": [],
        "stats": {"wins": 0, "losses": 0, "total_pnl": 0.0, "best": 0.0, "worst": 0.0},
        "paused": False,
        "current_price": 0.0,
        "last_update": "",
        "usdt_balance": 0.0,
        "btc_balance": 0.0,
        "uptime_start": _start_time,
        "last_heartbeat": int(time.time()),
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                saved = json.load(f)
                # Garante que subchaves de stats existam
                if 'stats' in saved and isinstance(saved['stats'], dict):
                    defaults['stats'].update(saved['stats'])
                    saved.pop('stats', None)
                defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_state(s):
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, indent=4)


# ── Controle manual (dashboard → bot) ────────────────────────────────────────
def read_command():
    if not os.path.exists(CONTROL_FILE):
        return None
    try:
        with open(CONTROL_FILE, 'r') as f:
            data = json.load(f)
        cmd = data.get('command')
        if cmd:
            with open(CONTROL_FILE, 'w') as f:
                json.dump({'command': None}, f)
        return cmd
    except Exception:
        return None


# ── Dados e saldo ─────────────────────────────────────────────────────────────
def get_data():
    try:
        # Aumentado para 300 para suportar o cálculo da SMA200
        ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=300)
        return pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    except Exception as e:
        log(f"Erro get_data: {e}")
        return None


def fetch_balances():
    try:
        bal  = exchange.fetch_balance()
        usdt = float(bal.get('USDT', {}).get('free', 0))
        asset = SYMBOL.split('/')[0]
        btc  = float(bal.get(asset, {}).get('free', 0))
        return usdt, btc
    except Exception:
        return 0.0, 0.0


# ── Log ───────────────────────────────────────────────────────────────────────
def log(msg):
    notify(msg)


def is_data_valid(df):
    if df is None or len(df) < 201:
        return False
    # Valida indicadores da estratégia Híbrida (Keltner + Didi + SMA200)
    cols_to_check = ['sma200', 'ema20', 'kc_lower', 'rsi', 'didi_short', 'didi_long', 'atr']
    if any(col not in df.columns for col in cols_to_check):
        return False
    
    # Verifica se a ÚLTIMA LINHA tem os dados necessários para o sinal
    if df[cols_to_check].iloc[-1].isnull().any():
        return False
        
    return True


def safe_order(order_func, *args, **kwargs):
    for attempt in range(3):
        try:
            return order_func(*args, **kwargs)
        except Exception as e:
            log(f"⚠️ Erro na ordem (tentativa {attempt+1}): {e}")
            time.sleep(2)
    return None


# ── Ordens ───────────────────────────────────────────────────────────────────
def buy(current_atr=None):
    try:
        price    = float(exchange.fetch_ticker(SYMBOL)['last'])
        usdt_bal, _ = fetch_balances()
        
        # Cálculo de Mão Profissional (ATR Based Risk)
        # Arriscamos X% do capital. A distância do stop é ATR * MULTIPLIER.
        risk_amount = usdt_bal * RISK_PER_TRADE_PCT
        
        if current_atr and current_atr > 0:
            stop_dist = current_atr * ATR_STOP_MULT
            amount = risk_amount / stop_dist
            # Limite de segurança: não usar mais que TRADE_SIZE_PCT do capital total
            max_amount = (usdt_bal * TRADE_SIZE_PCT) / price
            amount = min(amount, max_amount)
        else:
            # Fallback se não tiver ATR
            amount = (usdt_bal * TRADE_SIZE_PCT) / price

        if (amount * price) < 10:
            log(f"⚠️  Saldo insuficiente para risco calculado: ${amount*price:.2f} USDT")
            return

        safe_order(exchange.create_market_buy_order, SYMBOL, round(amount, 6))

        trade_log = list(bot_state.get("trade_log", []))
        trade_log.append({
            "type": "buy",
            "price": price,
            "amount": round(amount, 6),
            "value_usdt": round(amount * price, 2),
            "time": int(time.time()),
            "datetime": datetime.now().strftime("%d/%m %H:%M"),
        })
        bot_state.update({
            "position": "buy",
            "entry_price": price,
            "entry_atr": current_atr if current_atr else 0.0,
            "highest_since_entry": price,
            "candles_in_position": 0,
            "trade_log": trade_log[-50:],
            "last_trade_candle": bot_state.get("last_candle_time", 0),
        })
        save_state(bot_state)
        log(f"✅ COMPRA @ ${price:,.2f} | Mão: {amount:.4f} BTC (Risco: ${risk_amount:.2f})")
    except Exception as e:
        log(f"❌ Erro Compra: {e}")


def sell(exec_price=None, reason="sinal", size_pct=1.0):
    try:
        asset = SYMBOL.split('/')[0]
        _, btc_bal = fetch_balances()

        amount_to_sell = btc_bal * size_pct
        if amount_to_sell > 0.00001:
            safe_order(exchange.create_market_sell_order, SYMBOL, round(amount_to_sell, 6))

        sell_price = exec_price or float(exchange.fetch_ticker(SYMBOL)['last'])
        entry      = bot_state.get("entry_price", sell_price)
        pnl_pct    = round(((sell_price - entry) / entry * 100) if entry > 0 else 0, 3)

        # Atualiza estatísticas
        stats = bot_state.get("stats", {"wins": 0, "losses": 0, "total_pnl": 0.0, "best": 0.0, "worst": 0.0})
        if pnl_pct >= 0:
            stats['wins']  = stats.get('wins', 0) + 1
            stats['best']  = max(stats.get('best', 0.0), pnl_pct)
        else:
            stats['losses'] = stats.get('losses', 0) + 1
            stats['worst']  = min(stats.get('worst', 0.0), pnl_pct)
        stats['total_pnl'] = round(stats.get('total_pnl', 0.0) + pnl_pct, 3)

        trade_log = list(bot_state.get("trade_log", []))
        trade_log.append({
            "type": "sell" if size_pct == 1.0 else "parcial",
            "price": sell_price,
            "time": int(time.time()),
            "datetime": datetime.now().strftime("%d/%m %H:%M"),
            "pnl_pct": pnl_pct,
            "reason": reason,
            "size_pct": size_pct,
        })

        if size_pct == 1.0:
            bot_state.update({
                "position": None,
                "entry_price": 0.0,
                "partial_taken": False,
                "trade_log": trade_log[-50:],
                "stats": stats,
                "last_trade_candle": bot_state.get("last_candle_time", 0),
            })
        else:
            bot_state.update({
                "partial_taken": True,
                "trade_log": trade_log[-50:],
                "stats": stats,
            })

        save_state(bot_state)

        sign  = '+' if pnl_pct >= 0 else ''
        emoji = '🟢' if pnl_pct >= 0 else ('🟡' if size_pct < 1.0 else '🔴')
        pct_lbl = f" ({int(size_pct*100)}%)" if size_pct < 1.0 else ""
        log(f"{emoji} VENDA{pct_lbl} [{reason}] @ ${sell_price:,.2f} | P&L: {sign}{pnl_pct:.2f}%")
    except Exception as e:
        log(f"❌ Erro Venda: {e}")


# ── Loop principal ────────────────────────────────────────────────────────────
bot_state = load_state()
bot_state['uptime_start'] = _start_time
save_state(bot_state)

log("🤖 Robô iniciado [ESTRATÉGIA KELTNER 4H] — aguardando sinais...")

while True:
    try:
        # Comandos manuais (enviados pelo dashboard)
        cmd = read_command()
        if cmd == 'force_sell' and bot_state.get('position') == 'buy':
            log("⚡ Comando manual: FORCE SELL")
            sell(reason="manual")
        elif cmd == 'pause':
            bot_state['paused'] = True
            save_state(bot_state)
            log("⏸  Robô PAUSADO pelo dashboard")
        elif cmd == 'resume':
            bot_state['paused'] = False
            save_state(bot_state)
            log("▶️  Robô RETOMADO pelo dashboard")

        current_price = float(exchange.fetch_ticker(SYMBOL)['last'])
        usdt_bal, btc_bal = fetch_balances()

        # ── Gestão de posição: Parcial + Breakeven + Trailing + TP ─────────
        if bot_state["position"] == "buy":
            entry         = bot_state["entry_price"]
            entry_atr     = bot_state.get("entry_atr", 0.0)
            partial_taken = bot_state.get("partial_taken", False)
            candles_in_pos = bot_state.get("candles_in_position", 0)
            
            # Atualiza o pico máximo alcançado desde a entrada
            bot_state["highest_since_entry"] = max(bot_state.get("highest_since_entry", entry), current_price)
            highest = bot_state["highest_since_entry"]

            # --- GESTÃO DE RISCO DE ELITE (ALINHADA COM BACKTEST) ---
            # 1. Breakeven Precoce (trava no zero a zero antes da parcial)
            has_reached_breakeven = highest >= entry * config.BREAKEVEN_TRIGGER
            
            if partial_taken:
                # Se já garantiu 50% do lucro, encurta o stop para proteger o resto (1.5x ATR)
                stop_loss_price = entry  # Nunca perde dinheiro real
                trailing_price  = highest - (1.5 * entry_atr) if entry_atr > 0 else highest * config.TRAILING_PCT
            elif has_reached_breakeven:
                # Se bateu o gatilho, stop vai pro zero a zero
                stop_loss_price = entry
                trailing_price  = highest - (config.ATR_TRAILING_MULT * entry_atr) if entry_atr > 0 else highest * config.TRAILING_PCT
            else:
                # Stop inicial técnico
                stop_loss_price = entry - (config.ATR_STOP_MULT * entry_atr) if entry_atr > 0 else entry * config.STOP_LOSS
                trailing_price  = highest - (config.ATR_TRAILING_MULT * entry_atr) if entry_atr > 0 else highest * config.TRAILING_PCT

            current_stop = max(stop_loss_price, trailing_price)

            # --- VERIFICAÇÃO DE SAÍDAS ---
            # 1. Proteção (Stop / Trailing / Breakeven)
            if current_price <= current_stop:
                reason = "breakeven" if (has_reached_breakeven or partial_taken) and current_stop >= entry else "stop_loss"
                if current_stop > entry: reason = "trailing_stop"
                log(f"🛑 Saída de Proteção ({reason}) @ ${current_price:,.2f} (Stop: ${current_stop:,.2f})")
                sell(current_price, reason=reason, size_pct=1.0)
                time.sleep(4)
                continue

            # 2. Time Stop (Se em X barras não andou nada e não está protegido, sai)
            if candles_in_pos >= config.TIME_STOP_BARS and not has_reached_breakeven and not partial_taken:
                log(f"⏳ Time Stop: Trade não evoluiu em {config.TIME_STOP_BARS} candles. Saindo @ ${current_price:,.2f}")
                sell(current_price, reason="time_stop", size_pct=1.0)
                time.sleep(4)
                continue

            # 3. Realização parcial: vende 50% ao atingir o alvo Alvo 1
            if not partial_taken and current_price >= entry * config.PARTIAL_PROFIT_PCT:
                log(f"🎯 Realização Parcial ({config.PARTIAL_SIZE_PCT*100:.0f}%) @ ${current_price:,.2f}")
                sell(current_price, reason="parcial", size_pct=config.PARTIAL_SIZE_PCT)
                time.sleep(4)
                continue

            # 4. Take Profit final: alvo de tendência longa
            if current_price >= entry * TAKE_PROFIT:
                log(f"🚀 Take Profit Final @ ${current_price:,.2f}")
                sell(current_price, reason="take_profit", size_pct=1.0)
                time.sleep(4)
                continue

        # ── Indicadores e sinal ─────────────────────────────────────────────
        bot_state["last_heartbeat"] = int(time.time())
        df = get_data()
        df = apply_indicators(df) if df is not None and not df.empty else None
        if is_data_valid(df):

            bot_state.update({
                "current_price":  current_price,
                "usdt_balance":   round(usdt_bal, 2),
                "btc_balance":    round(btc_bal, 8),
                "last_update":    datetime.now().strftime("%H:%M:%S"),
                "last_update_ts": int(time.time()),
            })
            save_state(bot_state)

            new_candle = df['time'].iloc[-1] != bot_state["last_candle_time"]
            if new_candle and not bot_state.get('paused', False):
                signal = generate_signal(df)

                # Cooldown: não abre nova posição logo após um trade
                candles_since_trade = 0
                if bot_state.get("last_trade_candle"):
                    current_ts = int(df['time'].iloc[-1])
                    tf_ms = 4 * 60 * 60 * 1000  # 4h em ms
                    candles_since_trade = (current_ts - bot_state["last_trade_candle"]) // tf_ms
                cooldown_ok = candles_since_trade >= COOLDOWN_BARS or bot_state.get("last_trade_candle") == 0

                # Incrementa contador de candles na posição
                if bot_state["position"] == "buy":
                    bot_state["candles_in_position"] = bot_state.get("candles_in_position", 0) + 1

                rsi_str = f"RSI={df['rsi'].iloc[-1]:.1f}" if 'rsi' in df.columns and not pd.isna(df['rsi'].iloc[-1]) else ""
                hold_str = f"Hold={bot_state.get('candles_in_position',0)}/{MIN_HOLD_BARS}" if bot_state["position"] == "buy" else ""
                log(f"Candle ${df['close'].iloc[-1]:,.0f} | Sinal: {signal.upper()} | {rsi_str} | Cooldown: {'OK' if cooldown_ok else f'{candles_since_trade}/{COOLDOWN_BARS}'} {hold_str}")

                if signal == "buy" and bot_state["position"] is None and cooldown_ok:
                    buy(current_atr=df['atr'].iloc[-1])
                elif signal == "sell" and bot_state["position"] == "buy":
                    candles_held = bot_state.get("candles_in_position", 0)
                    if candles_held >= MIN_HOLD_BARS:
                        sell(float(df['close'].iloc[-1]), reason="sinal")
                    else:
                        log(f"⏳ Sinal de venda ignorado — {candles_held}/{MIN_HOLD_BARS} candles na posição")

                bot_state["last_candle_time"] = int(df['time'].iloc[-1])
                save_state(bot_state)

        else:
            log("⚠️ Dados inválidos ou atrasados. Aguardando...")
            save_state(bot_state)

        time.sleep(4)

    except Exception as e:
        log(f"Erro loop: {e}")
        time.sleep(5)
