API_KEY = "S87uKrR97EiYISlaWP0AYWaReJ7dvXp3Yk7Livag0OFjRRtRR7pmltka6ROSqy0b"
SECRET = "kavWgrtW1jenQ8FbF0hoJNkrChu0yFDyfygGRrA8HfPMHchPlI2bRMoKJRU25lPT"

SYMBOL = 'BTC/USDT'
TIMEFRAME = '5m'

# Com saldo baixo, não usamos valor fixo. O bot vai ler e usar 100% do seu saldo USDT.
# ATENÇÃO: Se puder depositar mais R$ 5 para passar de $10, o bot operará 100% sem riscos de rejeição da Binance.
STOP_LOSS = 0.98    # -2%
TAKE_PROFIT = 1.03  # +3%

STATE_FILE = 'bot_state.json'