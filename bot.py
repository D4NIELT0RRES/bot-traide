# bot.py

import ccxt
import pandas as pd
import time
import json
import os
from config import *
from strategy import apply_indicators, generate_signal

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}  # Mantido spot, mas otimizado para saldo baixo
})

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            print("⚠️ Erro ao ler arquivo de estado. Criando um novo.")
    return {"position": None, "entry_price": 0.0, "last_candle_time": 0}

def save_state(state_dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state_dict, f, indent=4)

bot_state = load_state()

def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=150)
    df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    return df

def get_price():
    return exchange.fetch_ticker(SYMBOL)['last']

def get_balance(asset):
    balance = exchange.fetch_balance()
    return balance.get(asset, {}).get('free', 0)

def buy():
    global bot_state
    price = get_price()
    usdt_balance = get_balance('USDT')

    # Alerta de segurança sobre as regras da Binance
    if usdt_balance < 1.0:
        print(f"❌ Saldo USDT zerado ou ínfimo ({usdt_balance:.2f} USDT).")
        return False

    print(f"💰 Saldo atual detectado: {usdt_balance:.2f} USDT. Usando margem total.")

    # Deduzimos uma taxa de segurança ligeiramente maior (0.7%) para garantir que a ordem passe
    # mesmo se o preço do BTC subir no milissegundo da execução.
    amount = (usdt_balance * 0.993) / price
    exchange.load_markets()
    amount = float(exchange.amount_to_precision(SYMBOL, amount))

    try:
        print(f"🛒 Enviando COMPRA de {amount} BTC (Total aprox: {usdt_balance:.2f} USDT)...")
        order = exchange.create_market_buy_order(SYMBOL, amount)
        
        executed_price = order.get('average', price) or price
        
        bot_state["position"] = "buy"
        bot_state["entry_price"] = float(executed_price)
        save_state(bot_state)
        
        print(f"✅ COMPRA EXECUTADA | Preço: {executed_price}")
        return True
    except Exception as e:
        print(f"🚨 Erro na Compra. Provavelmente saldo residual abaixo do mínimo da Binance: {e}")
        print("💡 Dica: Se depositar mais R$ 10, este erro sumirá permanentemente.")
        return False

def sell():
    global bot_state
    base_asset = SYMBOL.split('/')[0]
    balance = get_balance(base_asset)

    if balance <= 0:
        print("❌ Sem saldo em BTC para vender.")
        bot_state["position"] = None
        bot_state["entry_price"] = 0.0
        save_state(bot_state)
        return False

    exchange.load_markets()
    amount = float(exchange.amount_to_precision(SYMBOL, balance))
    
    try:
        print(f"🛒 Enviando VENDA de todo o saldo disponível: {amount} BTC...")
        exchange.create_market_sell_order(SYMBOL, amount)
        
        bot_state["position"] = None
        bot_state["entry_price"] = 0.0
        save_state(bot_state)
        
        print("💰 VENDA EXECUTADA COM SUCESSO!")
        return True
    except Exception as e:
        print(f"🚨 Falha ao vender: {e}")
        print("⚠️ Seu saldo pode ter ficado preso abaixo do mínimo devido às taxas de corretagem.")
        return False


print("🤖 Robô de Mínimo Ativo e Monitorando...")

while True:
    try:
        current_price = get_price()
        
        # Monitoramento em tempo real do Stop/Take
        if bot_state["position"] == "buy" and bot_state["entry_price"] > 0:
            if current_price <= bot_state["entry_price"] * STOP_LOSS:
                print(f"⚠️ STOP LOSS disparado! Preço entrada: {bot_state['entry_price']} | Atual: {current_price}")
                sell()
                continue
                
            elif current_price >= bot_state["entry_price"] * TAKE_PROFIT:
                print(f"🎯 TAKE PROFIT disparado! Preço entrada: {bot_state['entry_price']} | Atual: {current_price}")
                sell()
                continue

        # Análise técnica por fechamento de vela
        df = get_data()
        if df is None or df.empty:
            time.sleep(2)
            continue
            
        current_candle_time = df['time'].iloc[-1]
        
        if current_candle_time != bot_state["last_candle_time"]:
            df = apply_indicators(df)
            signal = generate_signal(df)
            rsi_closed = df['rsi'].iloc[-2]
            
            print(f"📊 [Vela Fechada] Sinal: {signal} | BTC: {current_price} | RSI: {rsi_closed:.2f}")
            
            if signal == "buy" and bot_state["position"] is None:
                buy()
            elif signal == "sell" and bot_state["position"] == "buy":
                sell()
                
            bot_state["last_candle_time"] = int(current_candle_time)
            save_state(bot_state)

        time.sleep(2)

    except ccxt.NetworkError as ne:
        print(f"⚠️ Erro de conexão na API: {ne}. Retentando em 10s...")
        time.sleep(10)
    except Exception as e:
        print(f"🚨 Erro no loop principal: {e}")
        time.sleep(5)