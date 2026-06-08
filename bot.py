# bot.py
import ccxt
import pandas as pd
import time
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from config import (
    API_KEY, SECRET, SYMBOL, TIMEFRAME,
    STOP_LOSS, TAKE_PROFIT, TRADE_SIZE_PCT,
    COOLDOWN_BARS, STATE_FILE, CONTROL_FILE
)
from strategy import apply_indicators, generate_signal

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

_start_time = int(time.time())


# ── Estado ────────────────────────────────────────────────────────────────────
def load_state():
    defaults = {
        "position": None,
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
        ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
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
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── Ordens ───────────────────────────────────────────────────────────────────
def buy():
    try:
        price    = float(exchange.fetch_ticker(SYMBOL)['last'])
        usdt_bal, _ = fetch_balances()
        usdt_use = usdt_bal * TRADE_SIZE_PCT

        if usdt_use < 10:
            log(f"⚠️  Saldo insuficiente: ${usdt_bal:.2f} USDT (mín $10)")
            return

        amount = usdt_use / price
        exchange.create_market_buy_order(SYMBOL, round(amount, 6))

        trade_log = list(bot_state.get("trade_log", []))
        trade_log.append({
            "type": "buy",
            "price": price,
            "amount": round(amount, 6),
            "value_usdt": round(usdt_use, 2),
            "time": int(time.time()),
            "datetime": datetime.now().strftime("%d/%m %H:%M"),
        })
        bot_state.update({
            "position": "buy",
            "entry_price": price,
            "trade_log": trade_log[-50:],
            "last_trade_candle": bot_state.get("last_candle_time", 0),
        })
        save_state(bot_state)
        log(f"✅ COMPRA @ ${price:,.2f} | ${usdt_use:.2f} USDT ({TRADE_SIZE_PCT*100:.0f}% saldo)")
    except Exception as e:
        log(f"❌ Erro Compra: {e}")


def sell(exec_price=None, reason="sinal"):
    try:
        asset = SYMBOL.split('/')[0]
        _, btc_bal = fetch_balances()

        if btc_bal > 0.00001:
            exchange.create_market_sell_order(SYMBOL, round(btc_bal, 6))

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
            "type": "sell",
            "price": sell_price,
            "time": int(time.time()),
            "datetime": datetime.now().strftime("%d/%m %H:%M"),
            "pnl_pct": pnl_pct,
            "reason": reason,
        })
        bot_state.update({
            "position": None,
            "entry_price": 0.0,
            "trade_log": trade_log[-50:],
            "stats": stats,
            "last_trade_candle": bot_state.get("last_candle_time", 0),
        })
        save_state(bot_state)

        sign  = '+' if pnl_pct >= 0 else ''
        emoji = '🟢' if pnl_pct >= 0 else '🔴'
        log(f"{emoji} VENDA [{reason}] @ ${sell_price:,.2f} | P&L: {sign}{pnl_pct:.2f}%")
    except Exception as e:
        log(f"❌ Erro Venda: {e}")


# ── Loop principal ────────────────────────────────────────────────────────────
bot_state = load_state()
bot_state['uptime_start'] = _start_time
save_state(bot_state)

log("🤖 Robô iniciado — aguardando sinais...")

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

        # ── Stop Loss / Take Profit ─────────────────────────────────────────
        if bot_state["position"] == "buy":
            entry = bot_state["entry_price"]
            if current_price <= entry * STOP_LOSS:
                log(f"🛑 Stop Loss @ ${current_price:,.2f}")
                sell(current_price, reason="stop_loss")
                time.sleep(4)
                continue
            if current_price >= entry * TAKE_PROFIT:
                log(f"🎯 Take Profit @ ${current_price:,.2f}")
                sell(current_price, reason="take_profit")
                time.sleep(4)
                continue

        # ── Indicadores e sinal ─────────────────────────────────────────────
        df = get_data()
        if df is not None and not df.empty:
            df = apply_indicators(df)

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
                    tf_ms = 15 * 60 * 1000
                    candles_since_trade = (current_ts - bot_state["last_trade_candle"]) // tf_ms
                cooldown_ok = candles_since_trade >= COOLDOWN_BARS or bot_state.get("last_trade_candle") == 0

                rsi_str = f"RSI={df['rsi'].iloc[-1]:.1f}" if 'rsi' in df.columns and not pd.isna(df['rsi'].iloc[-1]) else ""
                log(f"Candle ${df['close'].iloc[-1]:,.0f} | Sinal: {signal.upper()} | {rsi_str} | Cooldown: {'OK' if cooldown_ok else f'{candles_since_trade}/{COOLDOWN_BARS}'}")

                if signal == "buy" and bot_state["position"] is None and cooldown_ok:
                    buy()
                elif signal == "sell" and bot_state["position"] == "buy":
                    sell(float(df['close'].iloc[-1]), reason="sinal")

                bot_state["last_candle_time"] = int(df['time'].iloc[-1])
                save_state(bot_state)

        time.sleep(4)

    except Exception as e:
        log(f"Erro loop: {e}")
        time.sleep(5)
