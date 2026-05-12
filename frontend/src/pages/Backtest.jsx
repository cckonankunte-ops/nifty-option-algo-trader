import { useState } from 'react'
import axios from 'axios'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function Backtest() {
  const [form, setForm] = useState({
    start_date: '', end_date: '', initial_capital: 100000,
    signal_mode: 'SIMPLE_5MIN', candle_interval: '5',
    adx_period: 14, adx_threshold: 25, rsi_upper: 50, rsi_lower: 50,
    lot_sizing: 'fixed',
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

      <div className="space-y-6">
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

          {/* Candle Interval */}
          <div>
            <label className="text-xs text-gray-400 block mb-2">Candle Interval</label>
            <div className="flex gap-2">
              {[{v: '5', l: '5-min'}, {v: '15', l: '15-min'}, {v: '1', l: '1-min'}].map(opt => (
                <button key={opt.v}
                  onClick={() => setForm({...form, candle_interval: opt.v})}
                  className={`px-4 py-1.5 rounded text-sm ${form.candle_interval === opt.v ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                  {opt.l}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {form.candle_interval === '5' ? '5-min candles. More signals per day.' :
               form.candle_interval === '15' ? '15-min candles. Balanced signals.' :
               '1-min candles. Most signals, highest frequency.'}
            </p>
          </div>

          {/* Signal Mode */}
          <div>
            <label className="text-xs text-gray-400 block mb-2">Signal Mode</label>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" checked={form.signal_mode === 'SIMPLE_5MIN'} onChange={() => setForm({...form, signal_mode: 'SIMPLE_5MIN'})} />
                <span className="text-sm">Simple</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" checked={form.signal_mode === 'ADVANCED_5MIN_1MIN_ADX'} onChange={() => setForm({...form, signal_mode: 'ADVANCED_5MIN_1MIN_ADX'})} />
                <span className="text-sm">Advanced (ADX)</span>
              </label>
            </div>
          </div>

          {/* RSI Thresholds */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400">RSI Upper</label>
              <input type="number" value={form.rsi_upper} onChange={e => setForm({...form, rsi_upper: parseInt(e.target.value)})}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs text-gray-400">RSI Lower</label>
              <input type="number" value={form.rsi_lower} onChange={e => setForm({...form, rsi_lower: parseInt(e.target.value)})}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1" />
            </div>
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

          {/* Lot Sizing */}
          <div>
            <label className="text-xs text-gray-400 block mb-2">Lot Sizing</label>
            <div className="flex gap-2">
              <button onClick={() => setForm({...form, lot_sizing: 'fixed'})}
                className={`px-4 py-1.5 rounded text-sm ${form.lot_sizing === 'fixed' ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                Fixed (Initial Capital)
              </button>
              <button onClick={() => setForm({...form, lot_sizing: 'compounding'})}
                className={`px-4 py-1.5 rounded text-sm ${form.lot_sizing === 'compounding' ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                Compounding
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {form.lot_sizing === 'fixed' ? 'Always calculate lots from initial capital (consistent risk)' : 'Calculate lots from current capital (profits increase position size)'}
            </p>
          </div>

          <button onClick={run} disabled={loading} className="w-full bg-green-600 hover:bg-green-700 py-2 rounded font-medium disabled:opacity-50">
            {loading ? 'Running...' : 'Run Backtest'}
          </button>
        </div>

        {/* Results */}
        <div className="bg-gray-800 rounded p-4">
          {!result && <p className="text-gray-500 text-sm">Run a backtest to see results</p>}
          {result && (
            <div className="space-y-4">
              {/* Total P&L highlight */}
              <div className="flex items-center gap-6 pb-3 border-b border-gray-700">
                <div>
                  <span className="text-gray-400 text-xs">Gross P&L</span>
                  <div className={`text-2xl font-bold ${(result.metrics.final_capital - result.metrics.initial_capital) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ₹{((result.metrics.final_capital || 0) - (result.metrics.initial_capital || 0)).toLocaleString('en-IN', {maximumFractionDigits: 0})}
                  </div>
                </div>
                <div>
                  <span className="text-gray-400 text-xs">Charges</span>
                  <div className="text-2xl font-bold text-orange-400">
                    -₹{(result.metrics.total_charges || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}
                  </div>
                </div>
                <div>
                  <span className="text-gray-400 text-xs">Net P&L</span>
                  <div className={`text-2xl font-bold ${(result.metrics.net_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ₹{(result.metrics.net_pnl || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}
                  </div>
                </div>
                <div>
                  <span className="text-gray-400 text-xs">Return</span>
                  <div className={`text-2xl font-bold ${result.metrics.total_return_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {result.metrics.total_return_percent}%
                  </div>
                </div>
                <div>
                  <span className="text-gray-400 text-xs">Capital</span>
                  <div className="text-lg text-white">₹{(result.metrics.initial_capital || 0).toLocaleString('en-IN')} → ₹{(result.metrics.final_capital || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}</div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 text-sm">
                <div><span className="text-gray-400">Win Rate:</span> {result.metrics.win_rate}%</div>
                <div><span className="text-gray-400">Trades:</span> {result.metrics.total_trades}</div>
                <div><span className="text-gray-400">Max DD:</span> {result.metrics.max_drawdown}%</div>
                <div><span className="text-gray-400">Sharpe:</span> {result.metrics.sharpe_ratio}</div>
                <div><span className="text-gray-400">Interval:</span> {result.metrics.candle_interval || 'daily'}</div>
                <div><span className="text-gray-400">Lot Size:</span> 65 × {result.metrics.total_trades > 0 ? '1 lot' : '0'}</div>
                {result.metrics.adx_filtered_count > 0 && (
                  <div><span className="text-gray-400">ADX Filtered:</span> {result.metrics.adx_filtered_count}</div>
                )}
              </div>

              {/* Equity Curve */}
              {result.equity_curve?.length > 0 && (
                <div>
                  <h4 className="text-xs text-gray-400 mb-1">Equity Curve</h4>
                  <ResponsiveContainer width="100%" height={150}>
                    <LineChart data={result.equity_curve}>
                      <XAxis dataKey="timestamp" hide />
                      <YAxis domain={['auto', 'auto']} />
                      <Tooltip />
                      <Line type="monotone" dataKey="value" stroke="#10b981" dot={false} strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Daily P&L Bar Chart */}
              {result.daily_pnl?.length > 0 && (
                <div>
                  <h4 className="text-xs text-gray-400 mb-1">Daily P&L</h4>
                  <ResponsiveContainer width="100%" height={150}>
                    <BarChart data={result.daily_pnl}>
                      <XAxis dataKey="date" tick={{fontSize: 10}} />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="pnl">
                        {result.daily_pnl.map((entry, idx) => (
                          <Cell key={idx} fill={entry.pnl >= 0 ? '#10b981' : '#ef4444'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Trade Log */}
              {result.trade_log?.length > 0 && (
                <div className="max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="text-gray-400 sticky top-0 bg-gray-800">
                      <tr>
                        <th className="text-left py-1">Date</th>
                        <th className="text-left">Entry</th>
                        <th className="text-left">Exit</th>
                        <th>Signal</th>
                        <th>Strike</th>
                        <th>Qty</th>
                        <th>Entry ₹</th>
                        <th>Exit ₹</th>
                        <th>P&L</th>
                        <th>Max Loss</th>
                        <th>Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.trade_log.map((t, i) => (
                        <tr key={i} className="border-t border-gray-700">
                          <td className="py-1">{t.entry_time?.slice(0, 10)}</td>
                          <td>{t.entry_time?.slice(11, 16)}</td>
                          <td>{t.exit_time?.slice(11, 16)}</td>
                          <td className="text-center">{t.signal === 'BUY_CALL' ? 'CE' : 'PE'}</td>
                          <td className="text-center">{t.strike || '-'}</td>
                          <td className="text-center">{t.quantity || 65}</td>
                          <td className="text-center">{t.entry_price?.toFixed(1)}</td>
                          <td className="text-center">{t.exit_price?.toFixed(1)}</td>
                          <td className={`text-center ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>₹{t.pnl?.toFixed(0)}</td>
                          <td className="text-center text-yellow-400">₹{Math.round((form.initial_capital || 100000) * 0.06)}</td>
                          <td className="text-center">{t.exit_reason}</td>
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
