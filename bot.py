import ccxt, time, json, os, pandas as pd
from config import *
from strategy import apply_indicators, generate_signal

exchange = ccxt.binance({'apiKey': API_KEY, 'secret': SECRET, 'enableRateLimit': True})

def load_state():
    defaults = {"position": None, "entry_price": 0.0, "high_price": 0.0, "last_candle_time": 0}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                saved = json.load(f)
                defaults.update(saved)
            except: pass
    return defaults

def save_state(state):
    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=4)

bot_state = load_state()

def buy():
    price = exchange.fetch_ticker(SYMBOL)['last']
    balance = exchange.fetch_balance().get('USDT', {}).get('free', 0)
    if balance < 10: return False 
    
    amount = (balance * 0.99) / price
    exchange.create_market_buy_order(SYMBOL, amount)
    bot_state.update({"position": "buy", "entry_price": price, "high_price": price})
    save_state(bot_state)

def sell():
    base_asset = SYMBOL.split('/')[0]
    balance = exchange.fetch_balance().get(base_asset, {}).get('free', 0)
    if balance > 0:
        exchange.create_market_sell_order(SYMBOL, balance)
        bot_state.update({"position": None, "entry_price": 0.0, "high_price": 0.0})
        save_state(bot_state)

while True:
    try:
        current_price = exchange.fetch_ticker(SYMBOL)['last']
        
        # Trailing Stop
        if bot_state["position"] == "buy":
            bot_state["high_price"] = max(bot_state["high_price"], current_price)
            if current_price <= bot_state["entry_price"] * STOP_LOSS or \
               current_price <= bot_state["high_price"] * (1 - TRAILING_STOP_PCT):
                sell()
        
        ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        if df['time'].iloc[-1] != bot_state["last_candle_time"]:
            df = apply_indicators(df)
            signal = generate_signal(df)
            if signal == "buy" and not bot_state["position"]: buy()
            elif signal == "sell" and bot_state["position"]: sell()
            bot_state["last_candle_time"] = int(df['time'].iloc[-1])
            save_state(bot_state)
            
        time.sleep(10)
    except Exception as e:
        print(f"Erro: {e}")
        time.sleep(10)