import { useState } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function Backtest() {
  const [form, setForm] = useState({
    start_date: '', end_date: '', initial_capital: 100000,
    signal_mode: 'SIMPLE_5MIN', adx_period: 14, adx_threshold: 25,
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    setLoading(true)
    try {
      const res = await axios.post('/api/backtest/run', form)
      setResult(res.data)
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Backtest</h2>

      <div className="grid grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="bg-gray-800 rounded p-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400">Start Date</label>
              <input type="date" value={form.start_date} onChange={e => setForm({...form, start_date: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs text-gray-400">End Date</label>
              <input type="date" value={form.end_date} onChange={e => setForm({...form, end_date: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400">Initial Capital (₹)</label>
            <input type="number" value={form.initial_capital} onChange={e => setForm({...form, initial_capital: parseFloat(e.target.value)})}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1" />
          </div>

          {/* Signal Mode */}
          <div className="flex gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="radio" checked={form.signal_mode === 'SIMPLE_5MIN'} onChange={() => setForm({...form, signal_mode: 'SIMPLE_5MIN'})} />
              <span className="text-sm">Simple 5-min</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="radio" checked={form.signal_mode === 'ADVANCED_5MIN_1MIN_ADX'} onChange={() => setForm({...form, signal_mode: 'ADVANCED_5MIN_1MIN_ADX'})} />
              <span className="text-sm">5-min+1min+ADX</span>
            </label>
          </div>

          {form.signal_mode === 'ADVANCED_5MIN_1MIN_ADX' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400">ADX Period</label>
                <input type="number" value={form.adx_period} onChange={e => setForm({...form, adx_period: parseInt(e.target.value)})}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1" />
              </div>
              <div>
                <label className="text-xs text-gray-400">ADX Threshold</label>
                <input type="number" value={form.adx_threshold} onChange={e => setForm({...form, adx_threshold: parseInt(e.target.value)})}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1" />
              </div>
            </div>
          )}

          <button onClick={run} disabled={loading} className="w-full bg-green-600 hover:bg-green-700 py-2 rounded font-medium disabled:opacity-50">
            {loading ? 'Running...' : 'Run Backtest'}
          </button>
        </div>

        {/* Results */}
        <div className="bg-gray-800 rounded p-4">
          {!result && <p className="text-gray-500 text-sm">Run a backtest to see results</p>}
          {result && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div><span className="text-gray-400">Return:</span> <span className="text-green-400">{result.metrics.total_return_percent}%</span></div>
                <div><span className="text-gray-400">Win Rate:</span> {result.metrics.win_rate}%</div>
                <div><span className="text-gray-400">Trades:</span> {result.metrics.total_trades}</div>
                <div><span className="text-gray-400">Max DD:</span> {result.metrics.max_drawdown}%</div>
                <div><span className="text-gray-400">Sharpe:</span> {result.metrics.sharpe_ratio}</div>
                <div><span className="text-gray-400">Mode:</span> {result.metrics.signal_mode}</div>
                {result.metrics.adx_filtered_count > 0 && (
                  <div><span className="text-gray-400">ADX Filtered:</span> {result.metrics.adx_filtered_count}</div>
                )}
              </div>

              {/* Equity Curve */}
              {result.equity_curve?.length > 0 && (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={result.equity_curve}>
                    <XAxis dataKey="timestamp" hide />
                    <YAxis domain={['auto', 'auto']} />
                    <Tooltip />
                    <Line type="monotone" dataKey="value" stroke="#10b981" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}

              {/* Trade Log */}
              {result.trade_log?.length > 0 && (
                <div className="max-h-48 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="text-gray-400">
                      <tr><th>Time</th><th>Signal</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Trigger</th></tr>
                    </thead>
                    <tbody>
                      {result.trade_log.map((t, i) => (
                        <tr key={i} className="border-t border-gray-700">
                          <td className="py-1">{t.entry_time?.slice(0, 16)}</td>
                          <td>{t.signal}</td>
                          <td>{t.entry_price?.toFixed(1)}</td>
                          <td>{t.exit_price?.toFixed(1)}</td>
                          <td className={t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>{t.pnl?.toFixed(0)}</td>
                          <td>{t.trigger_type}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
