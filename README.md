# Nifty Options Algo Trader

Automated algorithmic trading for Nifty Options (Buy Call / Buy Put) on the Indian NSE market. Zero human intervention during trading hours — just Start/Stop and fund input.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, DhanHQ SDK, pandas-ta, APScheduler, SQLAlchemy
- **Frontend**: React 18 + Vite, TailwindCSS, Recharts
- **Broker**: Dhan (DhanHQ API)

## Setup

### 1. Create Dhan Account
- Log in to Dhan app or web at https://dhan.co
- Go to My Profile → Access Token
- Generate a new access token (valid for 30 days)
- Copy your Client ID and Access Token

### 2. Backend Setup
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Dhan credentials:
# DHAN_CLIENT_ID=your_client_id
# DHAN_ACCESS_TOKEN=your_access_token
# DHAN_SANDBOX_MODE=true  ← set to false for live trading
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
