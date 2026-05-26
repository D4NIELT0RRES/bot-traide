# 🤖 Bot de Bitcoin — BTC/USDT

Bot automatizado de trading de Bitcoin na Binance, com gestão de risco ativa via **Trailing Stop** e sinalização baseada no **Didi Index**.

---

## 📋 O que o sistema faz

O bot roda 24 horas por dia monitorando o mercado de Bitcoin a cada **10 segundos**. Quando as condições da estratégia se alinham em uma nova vela de **5 minutos**, ele executa a compra ou venda automaticamente na sua conta da Binance.

Em paralelo, você pode abrir um **dashboard no navegador** (http://localhost:8080) para acompanhar tudo em tempo real — preço, indicadores, saldo, lucro/prejuízo e histórico de operações.

---

## 📁 Estrutura dos Arquivos

| Arquivo | O que faz |
|---|---|
| `bot.py` | O robô em si — roda o loop de trading automático |
| `strategy.py` | A lógica da estratégia (Didi Index + RSI) |
| `config.py` | Configurações: credenciais, par, timeframe e parâmetros de risco |
| `dashboard_server.py` | Servidor web do painel de monitoramento |
| `bot_state.json` | Estado persistente do bot (posição aberta, preço de entrada, etc.) |
| `.env` | Suas chaves da Binance (não commitar no git) |
| `.env.example` | Modelo para configurar o `.env` |
| `requirements.txt` | Dependências do projeto |

---

## ⚙️ Configurações Atuais (`config.py`)

| Parâmetro | Valor | O que significa |
|---|---|---|
| **Par** | BTC/USDT | Negocia Bitcoin contra dólar (USDT) |
| **Timeframe** | 5 minutos | Analisa velas de 5 em 5 minutos |
| **Stop Loss** | -2% | Vende se o preço cair 2% do ponto de entrada |
| **Take Profit** | +3% | Referência de lucro esperado |
| **Trailing Stop** | 1,5% | Vende se o preço recuar 1,5% do topo local após a compra |

---

## 📈 Estratégia Atual — Didi Index

A estratégia é baseada no **Didi Index**, criado pelo analista brasileiro Odir Aguiar (o "Didi"). Ela usa três **Médias Móveis Suavizadas de Welles Wilder (SMMA)** para identificar o exato momento em que uma tendência está começando — o chamado "Agulhada do Didi".

### O que é SMMA (Smooth Moving Average)?

Diferente da SMA simples, a SMMA dá mais peso para os preços mais recentes usando suavização exponencial (`alpha = 1 / período`). Isso a torna mais responsiva a movimentos novos e menos ruidosa que a EMA padrão.

| Média | Período | Papel |
|---|---|---|
| **SMMA3** | 3 candles | A "agulha" — reage rápido, cruza as outras quando há força |
| **SMMA8** | 8 candles | A "referência" — linha central que a SMMA3 cruza |
| **SMMA20** | 20 candles | A "âncora" — define a tendência macro |

---

### 🟢 Sinal de COMPRA — "Agulhada para cima"

O bot entra em posição quando as **três condições** acontecem juntas:

**1. Cruzamento de alta (SMMA3 cruza acima da SMMA8)**
> No candle anterior: `SMMA3 < SMMA8` (estavam desalinhadas)
> No candle atual: `SMMA3 > SMMA8` (cruzamento aconteceu — sinal de força)

**2. Âncora positiva (SMMA3 acima da SMMA20)**
> A SMMA3 está acima da média de longo prazo.
> Isso evita comprar em "falsos cruzamentos" durante tendências de baixa.

**3. RSI abaixo de 50 (não sobrecomprado)**
> O RSI (14 períodos) confirma que ainda há espaço para o preço subir.
> Filtro para evitar entrar em um ativo que já correu demais.

```
COMPRA = SMMA3 cruzou acima da SMMA8 + SMMA3 > SMMA20 + RSI < 50
```

---

### 🔴 Sinal de VENDA — Saída da posição

O bot sai da posição em **três situações**:

| Situação | Condição | Descrição |
|---|---|---|
| **Agulhada para baixo** | SMMA3 cruza abaixo da SMMA8 | A tendência de alta perdeu força — exit técnico |
| **RSI sobrecomprado** | RSI > 65 | O ativo está esticado, risco de reversão alto |
| **Trailing Stop** | Preço recuou 1,5% do topo | Proteção dinâmica de lucro (veja abaixo) |
| **Stop Loss fixo** | Preço caiu 2% da entrada | Proteção de capital em quedas rápidas |

---

### 🛡️ Trailing Stop — Proteção dinâmica de lucro

O Trailing Stop é diferente de um Take Profit fixo. Em vez de vender em um preço predefinido, ele **acompanha o preço conforme ele sobe** e só dispara se o mercado recuar.

**Como funciona:**
1. Logo após a compra, o bot registra o preço de entrada como `high_price`
2. A cada ciclo de 10 segundos, se o preço atual for maior que o `high_price`, ele atualiza o topo
3. Se o preço cair **1,5% abaixo do topo registrado**, o bot vende imediatamente

**Exemplo:**
```
Compra em:        R$ 100.000
Preço sobe até:   R$ 110.000  ← high_price atualizado
Trailing Stop:    R$ 110.000 × (1 - 0,015) = R$ 108.350
Se preço cair a:  R$ 108.350  → VENDA AUTOMÁTICA
Lucro capturado:  +8,35%  (em vez de esperar uma meta fixa)
```

---

### 📊 Fluxograma da estratégia

```
A cada nova vela (5 min):
        │
        ▼
   Calcula SMMA3, SMMA8, SMMA20, RSI
        │
        ├─ Sem posição aberta? ──▶  SMMA3 cruzou acima SMMA8?
        │                                    │
        │                               SIM + SMMA3 > SMMA20 + RSI < 50
        │                                    │
        │                                  COMPRA
        │
        └─ Com posição aberta? ──▶  A cada 10 segundos (Trailing Stop):
                                         │
                                    Atualiza high_price
                                         │
                              Preço caiu 1,5% do topo?  ──▶  VENDE
                              Preço caiu 2% da entrada?  ──▶  VENDE
                                         │
                              Na nova vela:
                              SMMA3 cruzou abaixo SMMA8?  ──▶  VENDE
                              RSI > 65?  ──▶  VENDE
```

---

## 🚀 Como rodar

### 1. Clonar e instalar dependências

```bash
# Criar e ativar o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows

# Instalar pacotes
pip install -r requirements.txt
```

### 2. Configurar credenciais da Binance

```bash
cp .env.example .env
```

Abra o arquivo `.env` e preencha com suas chaves:

```env
BINANCE_API_KEY=sua_chave_aqui
BINANCE_API_SECRET=seu_secret_aqui
```

> ⚠️ A API precisa ter permissão de **leitura** e **trading spot**. **Nunca ative permissão de saque.**

### 3. Rodar o bot

```bash
.venv/bin/python bot.py
```

### 4. Rodar o dashboard (opcional, em outro terminal)

```bash
.venv/bin/python dashboard_server.py
```

Acesse no navegador: **http://localhost:8080**

---

## 🖥️ Dashboard (painel web)

O painel mostra em tempo real:

- 💰 Preço atual do BTC
- 📊 RSI com barra visual
- 📡 Sinal atual (COMPRA / VENDA / HOLD)
- 📈 P&L da posição aberta (lucro ou prejuízo em % e USDT)
- 🎯 Níveis de Stop Loss e Trailing Stop
- 💼 Saldo de USDT e BTC
- 📋 Log de eventos (compras e vendas)
- 🟢🔴 Botões para comprar e vender manualmente

O dashboard atualiza automaticamente a cada **15 segundos**.

---

## ⚠️ Pontos importantes

- O bot opera no mercado **spot** (não é futures nem alavancagem)
- Só mantém **uma posição por vez**
- O estado é salvo em `bot_state.json` — se o bot for reiniciado com BTC na carteira, ele detecta a posição automaticamente e retoma o monitoramento do Trailing Stop
- O `bot_state.json` e o `.env` estão no `.gitignore` e **não são commitados no git**

---

## 🔧 Indicadores utilizados

| Indicador | Configuração | Função |
|---|---|---|
| **SMMA3** | 3 períodos (Welles Wilder) | Agulha rápida do Didi Index |
| **SMMA8** | 8 períodos (Welles Wilder) | Referência central do cruzamento |
| **SMMA20** | 20 períodos (Welles Wilder) | Âncora de tendência macro |
| **RSI** | 14 períodos | Filtro de sobrecompra/sobrevenda |

---

## 📦 Dependências

```
ccxt>=4.0.0        # Conexão com a Binance
ta>=0.10.0         # Cálculo de indicadores técnicos
pandas>=2.0.0      # Manipulação de dados OHLCV
python-dotenv>=1.0.0  # Leitura segura das credenciais
```
