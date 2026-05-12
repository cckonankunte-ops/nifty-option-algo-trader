import { useState, useEffect, useRef } from 'react'
import axios from 'axios'

export default function Dashboard() {
  const [status, setStatus] = useState(null)
  const [fund, setFund] = useState('100000')
  const [error, setError] = useState('')
  const [signalExpanded, setSignalExpanded] = useState(false)
  const [tradingMode, setTradingMode] = useState('paper')
  const [settings, setSettings] = useState({
    candle_interval: '5',
    signal_mode: 'SIMPLE_5MIN',
    rsi_upper: 55,
    rsi_lower: 45,
    sl_percent: 20,
    lot_sizing: 'fixed',
  })
  const ws = useRef(null)

  useEffect(() => {
    fetchStatus()
    connectWs()
    return () => { if (ws.current) ws.current.close() }
  }, [])

  const fetchStatus = async () => {
    try {
      const res = await axios.get('/api/trading/status')
      setStatus(res.data)
      if (res.data.paper_mode !== undefined) {
        setTradingMode(res.data.paper_mode ? 'paper' : 'live')
      }
    } catch (e) { console.error(e) }
  }

  const connectWs = () => {
    ws.current = new WebSocket(`ws://${window.location.host}/ws/live`)
    ws.current.onmessage = (e) => {
      const event = JSON.parse(e.data)
      if (event.type === 'TICK' || event.type === 'SIGNAL') fetchStatus()
    }
    ws.current.onclose = () => setTimeout(connectWs, 5000)
  }

  const startEngine = async () => {
    const amount = parseFloat(fund)
    if (!amount || amount <= 10000) {
      setError('Fund must be greater than ₹10,000')
      return
    }
    setError('')
    await axios.post('/api/trading/start', {
      fund_amount: amount,
      trading_mode: tradingMode,
      ...settings,
    })
    fetchStatus()
  }

  const stopEngine = async () => {
    await axios.post('/api/trading/stop')
    fetchStatus()
  }

  const isRunning = status?.status === 'RUNNING'

  return (
    <div className="space-y-6">
      {/* Trading Mode Banner */}
      {tradingMode === 'paper' && (
        <div className="bg-yellow-600/20 border border-yellow-500 text-yellow-300 px-4 py-2 rounded text-sm">
          ⚠️ Paper Trading Mode — orders are simulated, no real money used
        </div>
      )}
      {tradingMode === 'live' && (
        <div className="bg-red-600/20 border border-red-500 text-red-300 px-4 py-2 rounded text-sm">
          🔴 LIVE Trading Mode — real orders will be placed on Dhan
        </div>
      )}

      {/* Status + Mode Badge */}
      <div className="flex items-center gap-4">
        <span className={`px-3 py-1 rounded text-sm font-medium ${
          isRunning ? 'bg-green-600' : status?.status === 'DAILY_CAP_HIT' ? 'bg-red-600' : 'bg-gray-600'
        }`}>
          {status?.status || 'STOPPED'}
        </span>
        <span className="px-3 py-1 rounded bg-blue-600/30 text-blue-300 text-sm">
          {settings.candle_interval}-min | {settings.signal_mode === 'ADVANCED_5MIN_1MIN_ADX' ? 'ADX' : 'Simple'}
        </span>
        <span className={`px-3 py-1 rounded text-sm ${tradingMode === 'live' ? 'bg-red-600/30 text-red-300' : 'bg-yellow-600/30 text-yellow-300'}`}>
          {tradingMode === 'live' ? 'LIVE' : 'PAPER'}
        </span>
        <span className="text-gray-400 text-sm ml-auto">
          9:45 AM – 3:15 PM IST
        </span>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Today P&L" value={`₹${status?.today_pnl?.toFixed(2) || '0.00'}`} />
        <MetricCard label="Trades Today" value={status?.today_trades || 0} />
        <MetricCard label="Fund" value={`₹${parseFloat(fund || 0).toLocaleString('en-IN')}`} />
        <MetricCard label="Max Daily Loss" value={`₹${Math.round(parseFloat(fund || 100000) * 0.06).toLocaleString('en-IN')}`} />
      </div>

      {/* Trading Controls */}
      <div className="bg-gray-800 rounded p-4 space-y-4">
        <h3 className="text-sm font-medium text-gray-300">Trading Controls</h3>

        {/* Live / Paper Toggle */}
        <div>
          <label className="text-xs text-gray-400 block mb-2">Trading Mode</label>
          <div className="flex gap-2">
            <button onClick={() => setTradingMode('paper')} disabled={isRunning}
              className={`px-4 py-1.5 rounded text-sm ${tradingMode === 'paper' ? 'bg-yellow-600 text-white' : 'bg-gray-700 text-gray-300'} disabled:opacity-50`}>
              Paper Trade
            </button>
            <button onClick={() => setTradingMode('live')} disabled={isRunning}
              className={`px-4 py-1.5 rounded text-sm ${tradingMode === 'live' ? 'bg-red-600 text-white' : 'bg-gray-700 text-gray-300'} disabled:opacity-50`}>
              Live Trade
            </button>
          </div>
        </div>

        {/* Fund + Start/Stop */}
        <div className="flex items-center gap-4">
          <div>
            <label className="text-xs text-gray-400">Fund (₹)</label>
            <input type="number" value={fund} onChange={(e) => setFund(e.target.value)} disabled={isRunning}
              className="bg-gray-700 border border-gray-600 rounded px-3 py-1.5 w-40 text-white text-sm mt-1 disabled:opacity-50" />
          </div>
          <div className="pt-4">
            <button onClick={isRunning ? stopEngine : startEngine}
              className={`px-6 py-2 rounded font-medium ${isRunning ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'}`}>
              {isRunning ? 'Stop Engine' : 'Start Engine'}
            </button>
          </div>
          {error && <span className="text-red-400 text-sm pt-4">{error}</span>}
        </div>

        {/* Strategy Settings (same as backtest) */}
        {!isRunning && (
          <div className="border-t border-gray-700 pt-4 space-y-3">
            <h4 className="text-xs text-gray-400">Strategy Settings</h4>

            <div className="grid grid-cols-4 gap-3">
              {/* Candle Interval */}
              <div>
                <label className="text-xs text-gray-500">Interval</label>
                <div className="flex gap-1 mt-1">
                  {['1', '5', '15'].map(v => (
                    <button key={v} onClick={() => setSettings({...settings, candle_interval: v})}
                      className={`px-2 py-1 rounded text-xs ${settings.candle_interval === v ? 'bg-green-600' : 'bg-gray-700'}`}>
                      {v}m
                    </button>
                  ))}
                </div>
              </div>

              {/* RSI Upper */}
              <div>
                <label className="text-xs text-gray-500">RSI Upper</label>
                <input type="number" value={settings.rsi_upper} onChange={e => setSettings({...settings, rsi_upper: parseInt(e.target.value)})}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-xs mt-1" />
              </div>

              {/* RSI Lower */}
              <div>
                <label className="text-xs text-gray-500">RSI Lower</label>
                <input type="number" value={settings.rsi_lower} onChange={e => setSettings({...settings, rsi_lower: parseInt(e.target.value)})}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-xs mt-1" />
              </div>

              {/* SL % */}
              <div>
                <label className="text-xs text-gray-500">SL %</label>
                <input type="number" value={settings.sl_percent} onChange={e => setSettings({...settings, sl_percent: parseInt(e.target.value)})}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-xs mt-1" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {/* Signal Mode */}
              <div>
                <label className="text-xs text-gray-500">Signal Mode</label>
                <div className="flex gap-1 mt-1">
                  <button onClick={() => setSettings({...settings, signal_mode: 'SIMPLE_5MIN'})}
                    className={`px-3 py-1 rounded text-xs ${settings.signal_mode === 'SIMPLE_5MIN' ? 'bg-green-600' : 'bg-gray-700'}`}>
                    Simple
                  </button>
                  <button onClick={() => setSettings({...settings, signal_mode: 'ADVANCED_5MIN_1MIN_ADX'})}
                    className={`px-3 py-1 rounded text-xs ${settings.signal_mode === 'ADVANCED_5MIN_1MIN_ADX' ? 'bg-green-600' : 'bg-gray-700'}`}>
                    ADX
                  </button>
                </div>
              </div>

              {/* Lot Sizing */}
              <div>
                <label className="text-xs text-gray-500">Lot Sizing</label>
                <div className="flex gap-1 mt-1">
                  <button onClick={() => setSettings({...settings, lot_sizing: 'fixed'})}
                    className={`px-3 py-1 rounded text-xs ${settings.lot_sizing === 'fixed' ? 'bg-green-600' : 'bg-gray-700'}`}>
                    Fixed
                  </button>
                  <button onClick={() => setSettings({...settings, lot_sizing: 'compounding'})}
                    className={`px-3 py-1 rounded text-xs ${settings.lot_sizing === 'compounding' ? 'bg-green-600' : 'bg-gray-700'}`}>
                    Compound
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Last Signal Details */}
      {status?.last_signal && (
        <div className="bg-gray-800 rounded p-4">
          <button onClick={() => setSignalExpanded(!signalExpanded)}
            className="text-sm text-gray-300 hover:text-white">
            Last Signal: <span className="font-medium text-green-400">{status.last_signal.signal}</span>
            {signalExpanded ? ' ▲' : ' ▼'}
          </button>
          {signalExpanded && (
            <div className="mt-3 text-sm text-gray-400 space-y-1">
              <p>Reason: {status.last_signal.reason}</p>
              <p>EMA Fast: {status.last_signal.indicators?.ema_fast?.toFixed(2)}</p>
              <p>EMA Slow: {status.last_signal.indicators?.ema_slow?.toFixed(2)}</p>
              <p>RSI: {status.last_signal.indicators?.rsi?.toFixed(2)}</p>
              <p>VWAP: {status.last_signal.indicators?.vwap?.toFixed(2)}</p>
              <p>ADX: {status.last_signal.indicators?.adx?.toFixed(2) || 'N/A'}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MetricCard({ label, value }) {
  return (
    <div className="bg-gray-800 rounded p-4">
      <div className="text-gray-400 text-xs">{label}</div>
      <div className="text-xl font-semibold mt-1">{value}</div>
    </div>
  )
}
