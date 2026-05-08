import { useState, useEffect, useRef } from 'react'
import axios from 'axios'

export default function Dashboard() {
  const [status, setStatus] = useState(null)
  const [fund, setFund] = useState('')
  const [error, setError] = useState('')
  const [signalExpanded, setSignalExpanded] = useState(false)
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
    await axios.post('/api/trading/start', { fund_amount: amount })
    fetchStatus()
  }

  const stopEngine = async () => {
    await axios.post('/api/trading/stop')
    fetchStatus()
  }

  const isRunning = status?.status === 'RUNNING'

  return (
    <div className="space-y-6">
      {/* Paper Trading Banner */}
      {status?.trading_mode === 'paper' && (
        <div className="bg-yellow-600/20 border border-yellow-500 text-yellow-300 px-4 py-2 rounded text-sm">
          Paper Trading Mode — orders are simulated
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
          {status?.signal_mode === 'ADVANCED_5MIN_1MIN_ADX' ? '5-min+1min+ADX' : '5-min Simple'}
        </span>
        <span className="text-gray-400 text-sm ml-auto">
          Window: {status?.trading_window?.start || '09:45'} – {status?.trading_window?.end || '15:00'} IST
        </span>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Today P&L" value={`₹${status?.today_pnl?.toFixed(2) || '0.00'}`} />
        <MetricCard label="Trades Today" value={status?.today_trades || 0} />
        <MetricCard label="Fund" value={`₹${status?.fund_amount?.toLocaleString() || '0'}`} />
        <MetricCard label="Position" value={status?.status === 'RUNNING' ? 'Active' : 'None'} />
      </div>

      {/* Start/Stop Controls */}
      <div className="flex items-center gap-4">
        <input
          type="number"
          placeholder="Fund amount (min ₹10,000)"
          value={fund}
          onChange={(e) => setFund(e.target.value)}
          disabled={isRunning}
          className="bg-gray-800 border border-gray-600 rounded px-4 py-2 w-64 text-white disabled:opacity-50"
        />
        <button
          onClick={isRunning ? stopEngine : startEngine}
          className={`px-6 py-2 rounded font-medium ${
            isRunning ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'
          }`}
        >
          {isRunning ? 'Stop Engine' : 'Start Engine'}
        </button>
        {error && <span className="text-red-400 text-sm">{error}</span>}
      </div>

      {/* Last Signal Details */}
      {status?.last_signal && (
        <div className="bg-gray-800 rounded p-4">
          <button
            onClick={() => setSignalExpanded(!signalExpanded)}
            className="text-sm text-gray-300 hover:text-white"
          >
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
