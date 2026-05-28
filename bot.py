# bot.py
import ccxt
import pandas as pd
import time
import json
import os
from datetime import datetime
from config import *
from strategy import apply_indicators, generate_signal

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

def load_state():
    defaults = {
        "position": None,
        "entry_price": 0.0,
        "last_candle_time": 0,
        "trade_log": []
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                defaults.update(json.load(f))
        except: pass
    return defaults

def save_state(state_dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state_dict, f, indent=4)

bot_state = load_state()

def get_data():
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
        return pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    except: return None

def buy():
    try:
        price = exchange.fetch_ticker(SYMBOL)['last']
        balance = exchange.fetch_balance().get('USDT', {}).get('free', 0)
        if balance < 10: return
        amount = (balance * 0.99) / price
        exchange.create_market_buy_order(SYMBOL, amount)

        trade_log = list(bot_state.get("trade_log", []))
        trade_log.append({
            "type": "buy",
            "price": price,
            "time": int(time.time()),
            "datetime": datetime.now().strftime("%d/%m %H:%M")
        })
        bot_state.update({
            "position": "buy",
            "entry_price": price,
            "trade_log": trade_log[-50:]
        })
        save_state(bot_state)
        print(f"✅ COMPRA executada @ ${price:,.2f}")
    except Exception as e:
        print(f"Erro Compra: {e}")

def sell(exec_price=None):
    try:
        asset = SYMBOL.split('/')[0]
        balance = exchange.fetch_balance().get(asset, {}).get('free', 0)
        if balance > 0:
            exchange.create_market_sell_order(SYMBOL, balance)

        sell_price = exec_price or exchange.fetch_ticker(SYMBOL)['last']
        entry = bot_state.get("entry_price", sell_price)
        pnl_pct = round(((sell_price - entry) / entry * 100) if entry > 0 else 0, 3)

        trade_log = list(bot_state.get("trade_log", []))
        trade_log.append({
            "type": "sell",
            "price": sell_price,
            "time": int(time.time()),
            "datetime": datetime.now().strftime("%d/%m %H:%M"),
            "pnl_pct": pnl_pct
        })
        bot_state.update({
            "position": None,
            "entry_price": 0.0,
            "trade_log": trade_log[-50:]
        })
        save_state(bot_state)
        pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
        print(f"{pnl_emoji} VENDA executada @ ${sell_price:,.2f} | P&L: {'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}%")
    except Exception as e:
        print(f"Erro Venda: {e}")

print("🤖 [ROBÔ] Cérebro de ordens rodando em segundo plano...")

while True:
    try:
        current_price = exchange.fetch_ticker(SYMBOL)['last']

        if bot_state["position"] == "buy":
            if current_price <= bot_state["entry_price"] * STOP_LOSS:
                print(f"🛑 Stop Loss atingido @ ${current_price:,.2f}")
                sell(current_price)
                continue
            if current_price >= bot_state["entry_price"] * TAKE_PROFIT:
                print(f"🎯 Take Profit atingido @ ${current_price:,.2f}")
                sell(current_price)
                continue

        df = get_data()
        if df is not None and not df.empty:
            df = apply_indicators(df)

            bot_state.update({
                "current_price": current_price,
                "last_update": datetime.now().strftime("%H:%M:%S")
            })
            save_state(bot_state)

            if df['time'].iloc[-1] != bot_state["last_candle_time"]:
                signal = generate_signal(df)
                if signal == "buy" and bot_state["position"] is None:
                    buy()
                elif signal == "sell" and bot_state["position"] == "buy":
                    sell(float(df['close'].iloc[-1]))
                bot_state["last_candle_time"] = int(df['time'].iloc[-1])
                save_state(bot_state)

        time.sleep(4)
    except Exception as e:
        print(f"Erro no loop: {e}")
        time.sleep(5)
