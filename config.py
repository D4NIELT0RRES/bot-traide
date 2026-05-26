import os
from dotenv import load_dotenv

# Carrega chaves do arquivo .env
load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET = os.getenv('BINANCE_API_SECRET')

SYMBOL = 'BTC/USDT'
TIMEFRAME = '5m'

# Gerenciamento de Risco
STOP_LOSS = 0.98         # -2%
TAKE_PROFIT = 1.03       # +3%
TRAILING_STOP_PCT = 0.015 # 1.5% de recuo máximo

STATE_FILE = 'bot_state.json'