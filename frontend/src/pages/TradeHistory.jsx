import { useState, useEffect } from 'react'
import axios from 'axios'

export default function TradeHistory() {
  const [trades, setTrades] = useState([])
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ option_type: '', status: '', trigger_type: '', date_from: '', date_to: '' })
  const [summary, setSummary] = useState({ total_trades: 0, total_pnl: 0, total_charges: 0, winning: 0, losing: 0 })

  useEffect(() => { fetchTrades() }, [page, filters])

  const fetchTrades = async () => {
    try {
      const params = { page, page_size: 50, ...filters }
      Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
      const res = await axios.get('/api/history/trades', { params })
      setTrades(res.data.trades || [])

      // Calculate summary from returned trades
      const allTrades = res.data.trades || []
      const totalPnl = allTrades.reduce((sum, t) => sum + (t.pnl || 0), 0)
      const winning = allTrades.filter(t => t.pnl > 0).length
      const losing = allTrades.filter(t => t.pnl <= 0).length
      // Charges per trade: ~₹50 average (brokerage + STT + exchange + GST)
      const totalCharges = allTrades.length * 50
      setSummary({ total_trades: allTrades.length, total_pnl: totalPnl, total_charges: totalCharges, winning, losing })
    } catch (e) { console.error(e) }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Trade History</h2>

      {/* Filters */}
      <div className="flex gap-3 items-center flex-wrap">
        <input type="date" value={filters.date_from} onChange={e => setFilters({...filters, date_from: e.target.value})}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" placeholder="From" />
        <input type="date" value={filters.date_to} onChange={e => setFilters({...filters, date_to: e.target.value})}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" placeholder="To" />
        <select value={filters.option_type} onChange={e => setFilters({...filters, option_type: e.target.value})}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
          <option value="">All Types</option>
          <option value="CE">CE (Call)</option>
          <option value="PE">PE (Put)</option>
        </select>
        <select value={filters.trigger_type} onChange={e => setFilters({...filters, trigger_type: e.target.value})}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
          <option value="">All Modes</option>
          <option value="paper">Paper</option>
          <option value="live">Live</option>
        </select>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-5 gap-3">
        <div className="bg-gray-800 rounded p-3">
          <div className="text-gray-400 text-xs">Total Trades</div>
          <div className="text-lg font-semibold">{summary.total_trades}</div>
        </div>
        <div className="bg-gray-800 rounded p-3">
          <div className="text-gray-400 text-xs">Total P&L</div>
          <div className={`text-lg font-semibold ${summary.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ₹{summary.total_pnl.toLocaleString('en-IN', {maximumFractionDigits: 0})}
          </div>
        </div>
        <div className="bg-gray-800 rounded p-3">
          <div className="text-gray-400 text-xs">Charges</div>
          <div className="text-lg font-semibold text-orange-400">₹{summary.total_charges.toLocaleString('en-IN')}</div>
        </div>
        <div className="bg-gray-800 rounded p-3">
          <div className="text-gray-400 text-xs">Net P&L</div>
          <div className={`text-lg font-semibold ${(summary.total_pnl - summary.total_charges) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ₹{(summary.total_pnl - summary.total_charges).toLocaleString('en-IN', {maximumFractionDigits: 0})}
          </div>
        </div>
        <div className="bg-gray-800 rounded p-3">
          <div className="text-gray-400 text-xs">Win/Loss</div>
          <div className="text-lg font-semibold">{summary.winning}W / {summary.losing}L</div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-gray-800 rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-700 text-gray-300">
            <tr>
              <th className="px-3 py-2 text-left">Date</th>
              <th className="px-3 py-2">Entry</th>
              <th className="px-3 py-2">Exit</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Strike</th>
              <th className="px-3 py-2">Qty</th>
              <th className="px-3 py-2">Entry ₹</th>
              <th className="px-3 py-2">Exit ₹</th>
              <th className="px-3 py-2">P&L</th>
              <th className="px-3 py-2">Reason</th>
              <th className="px-3 py-2">Mode</th>
            </tr>
          </thead>
          <tbody>
            {trades.map(t => (
              <tr key={t.id} className="border-t border-gray-700">
                <td className="px-3 py-2 text-xs">{t.entry_time?.slice(0, 10)}</td>
                <td className="px-3 py-2 text-center text-xs">{t.entry_time?.slice(11, 16)}</td>
                <td className="px-3 py-2 text-center text-xs">{t.exit_time?.slice(11, 16) || '-'}</td>
                <td className="px-3 py-2 text-center">{t.option_type}</td>
                <td className="px-3 py-2 text-center">{t.strike}</td>
                <td className="px-3 py-2 text-center">{t.quantity}</td>
                <td className="px-3 py-2 text-center">{t.entry_price?.toFixed(1)}</td>
                <td className="px-3 py-2 text-center">{t.exit_price?.toFixed(1) || '-'}</td>
                <td className={`px-3 py-2 text-center ${(t.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  ₹{t.pnl?.toFixed(0) || '0'}
                </td>
                <td className="px-3 py-2 text-center text-xs">{t.exit_reason || '-'}</td>
                <td className="px-3 py-2 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs ${t.trigger_type === 'live' ? 'bg-red-600/30 text-red-300' : 'bg-yellow-600/30 text-yellow-300'}`}>
                    {t.trigger_type || 'paper'}
                  </span>
                </td>
              </tr>
            ))}
            {trades.length === 0 && (
              <tr><td colSpan="11" className="px-3 py-8 text-center text-gray-500">No trades found</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex gap-2">
        <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
          className="px-3 py-1 bg-gray-700 rounded text-sm disabled:opacity-50">Prev</button>
        <span className="px-3 py-1 text-sm text-gray-400">Page {page}</span>
        <button onClick={() => setPage(page + 1)} disabled={trades.length < 50}
          className="px-3 py-1 bg-gray-700 rounded text-sm disabled:opacity-50">Next</button>
      </div>
    </div>
  )
}
