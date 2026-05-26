# 🤖 Bot de Bitcoin — BTC/USDT

Bot automatizado de trading de Bitcoin na Binance, com dashboard web em tempo real para monitoramento e operações manuais.

---

## 📋 O que o sistema faz

O bot roda 24 horas por dia e fica olhando o mercado de Bitcoin a cada **1 minuto**. Quando as condições certas aparecem, ele compra ou vende BTC automaticamente na sua conta da Binance.

Em paralelo, você pode abrir um **dashboard no navegador** (http://localhost:8080) para acompanhar tudo em tempo real — preço, indicadores, saldo, lucro/prejuízo e histórico de operações.

---

## 📁 Estrutura dos Arquivos

| Arquivo | O que faz |
|---|---|
| `bot.py` | O robô em si — roda o loop de trading automático |
| `strategy.py` | A lógica da estratégia (quando comprar e quando vender) |
| `config.py` | Configurações: API Key, par, valor por trade, stop e take profit |
| `dashboard_server.py` | Servidor web do painel de monitoramento |

---

## ⚙️ Configurações Atuais (`config.py`)

| Parâmetro | Valor | O que significa |
|---|---|---|
| **Par** | BTC/USDT | Negocia Bitcoin contra dólar (USDT) |
| **Timeframe** | 5 minutos | Analisa velas de 5 em 5 minutos |
| **Valor por trade** | $5 USDT | Quanto investe em cada compra |
| **Stop Loss** | -2% | Vende no prejuízo se o preço cair 2% do ponto de entrada |
| **Take Profit** | +3% | Vende no lucro se o preço subir 3% do ponto de entrada |

---

## 📈 Estratégia Atual

A estratégia combina **três indicadores** para decidir quando entrar e sair do mercado. Ela é conservadora: só compra quando os três fatores estão alinhados ao mesmo tempo.

---

### 🟢 Sinal de COMPRA

O bot compra quando as **três condições abaixo** acontecem juntas:

**1. Tendência de alta confirmada (SMA50)**
> O preço atual está acima da média dos últimos 50 candles (SMA50), **e** essa média está subindo. Isso filtra o mercado: o bot só compra em tendência de alta, nunca quando o mercado está caindo.

**2. RSI abaixo de 40 (pullback)**
> O RSI (14 períodos) está abaixo de 40. Isso indica que o preço deu uma pequena recuada dentro da tendência de alta — é o ponto de entrada, comprando "na baixa" durante uma tendência positiva.

**3. Volume acima da média**
> O volume do candle atual está maior que a média dos últimos 20 candles. Volume alto confirma que o movimento é real e não uma falsa oscilação.

```
COMPRA = Tendência de alta + RSI < 40 + Volume acima da média
```

---

### 🔴 Sinal de VENDA

O bot vende em **três situações diferentes**:

| Situação | Condição | Descrição |
|---|---|---|
| **Sinal da estratégia** | RSI > 65 | O ativo ficou sobrecomprado — hora de realizar lucro |
| **Take Profit** | Preço subiu +3% | Meta de lucro atingida |
| **Stop Loss** | Preço caiu -2% | Corte de perda automático para proteger o capital |

---

### 📊 Resumo visual da estratégia

```
Mercado em tendência de alta?  ──── NÃO ──▶  HOLD (aguarda)
         │
        SIM
         │
    RSI < 40?  ──── NÃO ──▶  HOLD (aguarda)
         │
        SIM
         │
  Volume alto?  ──── NÃO ──▶  HOLD (aguarda)
         │
        SIM
         │
       COMPRA  ──▶  Monitora: Stop -2% | Take Profit +3% | RSI > 65
```

---

## 🖥️ Dashboard (painel web)

Rode em paralelo com o bot para monitorar tudo:

```bash
python dashboard_server.py
```

Acesse no navegador: **http://localhost:8080**

O painel mostra:
- 💰 Preço atual do BTC
- 📊 RSI com barra visual
- 📡 Sinal atual (COMPRA / VENDA / HOLD)
- 📈 P&L da posição aberta (lucro ou prejuízo em % e USDT)
- 🎯 Níveis de Stop Loss e Take Profit
- 💼 Saldo de USDT e BTC
- 📋 Log de eventos (compras, vendas detectadas)
- 🟢🔴 Botões para comprar e vender manualmente

O dashboard atualiza automaticamente a cada **15 segundos**.

---

## 🚀 Como rodar

### 1. Instalar as dependências
```bash
pip install ccxt ta pandas
```

### 2. Configurar a API Key
No arquivo `config.py`, coloque sua API Key e Secret da Binance.

> ⚠️ A API precisa ter permissão de **leitura** e **trading spot**. Nunca ative permissão de saque.

### 3. Rodar o bot
```bash
python bot.py
```

### 4. Rodar o dashboard (opcional, em outro terminal)
```bash
python dashboard_server.py
```

---

## ⚠️ Pontos importantes

- O bot opera no mercado **spot** (não é futures/alavancagem)
- Cada operação usa **$5 USDT** — valor pequeno para testes
- O Stop Loss protege contra quedas bruscas (-2%)
- O bot só mantém **uma posição por vez**
- Se o bot for reiniciado enquanto há BTC na carteira, ele detecta a posição automaticamente e continua monitorando o stop/take profit

---

## 🔧 Indicadores utilizados

| Indicador | Configuração | Função |
|---|---|---|
| **RSI** | 14 períodos | Mede se o ativo está sobrecomprado ou sobrevendido |
| **SMA** | 50 períodos | Identifica a direção da tendência |
| **Volume** | Média de 20 candles | Confirma se o movimento tem força |
# bot-traide
