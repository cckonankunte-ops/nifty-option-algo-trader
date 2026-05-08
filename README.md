# Nifty Options Algo Trader

Automated algorithmic trading for Nifty Options (Buy Call / Buy Put) on the Indian NSE market. Zero human intervention during trading hours — just Start/Stop and fund input.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, fyers-apiv3, pandas-ta, APScheduler, SQLAlchemy
- **Frontend**: React 18 + Vite, TailwindCSS, Recharts
- **Broker**: Fyers API v3

## Setup

### 1. Create Fyers Account
- Register at [Fyers](https://myapi.fyers.in/)
- Create an API app and note your App ID and Secret Key

### 2. Backend Setup
```bash
cd backend
pip install -r ../requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Fyers credentials
```

### 4. Run Database Migrations
```bash
alembic upgrade head
```

### 5. Start Backend
```bash
uvicorn backend.main:app --reload
```

### 6. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## Trading Modes

- **Paper Trading** (default): Simulates orders without calling Fyers API
- **Live Trading**: Places real orders via Fyers API

Set `TRADING_MODE=paper` or `TRADING_MODE=live` in `.env`

## Signal Modes

- **SIMPLE_5MIN**: EMA crossover + RSI + VWAP on 5-min candles
- **ADVANCED_5MIN_1MIN_ADX**: 5-min trend + ADX filter + 1-min entry confirmation
