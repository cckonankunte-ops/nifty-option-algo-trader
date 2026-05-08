import { useState, useEffect } from 'react'
import axios from 'axios'

export default function TradeHistory() {
  const [trades, setTrades] = useState([])
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ option_type: '', status: '' })

  useEffect(() => { fetchTrades() }, [page, filters])

  const fetchTrades = async () => {
    try {
      const params = { page, page_size: 20, ...filters }
      Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
      const res = await axios.get('/api/history/trades', { params })
      setTrades(res.data.trades || [])
    } catch (e) { console.error(e) }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Trade History</h2>

      {/* Filters */}
      <div className="flex gap-3 items-center">
        <select value={filters.option_type} onChange={e => setFilters({...filters, option_type: e.target.value})}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
          <option value="">All Types</option>
          <option value="CE">CE (Call)</option>
          <option value="PE">PE (Put)</option>
        </select>
        <select value={filters.status} onChange={e => setFilters({...filters, status: e.target.value})}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
          <option value="">All Status</option>
          <option value="CLOSED">Closed</option>
          <option value="SQUARED_OFF">Squared Off</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-gray-800 rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-700 text-gray-300">
            <tr>
              <th className="px-3 py-2 text-left">Time</th>
              <th className="px-3 py-2 text-left">Symbol</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Entry</th>
              <th className="px-3 py-2">Exit</th>
              <th className="px-3 py-2">P&L</th>
              <th className="px-3 py-2">Reason</th>
            </tr>
          </thead>
          <tbody>
            {trades.map(t => (
              <tr key={t.id} className="border-t border-gray-700">
                <td className="px-3 py-2 text-xs">{t.entry_time?.slice(0, 16)}</td>
                <td className="px-3 py-2">{t.symbol}</td>
                <td className="px-3 py-2 text-center">{t.option_type}</td>
                <td className="px-3 py-2 text-center">{t.entry_price?.toFixed(1)}</td>
                <td className="px-3 py-2 text-center">{t.exit_price?.toFixed(1) || '-'}</td>
                <td className={`px-3 py-2 text-center ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  ₹{t.pnl?.toFixed(0) || '-'}
                </td>
                <td className="px-3 py-2 text-center text-xs">{t.exit_reason || '-'}</td>
              </tr>
            ))}
            {trades.length === 0 && (
              <tr><td colSpan="7" className="px-3 py-8 text-center text-gray-500">No trades found</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex gap-2">
        <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
          className="px-3 py-1 bg-gray-700 rounded text-sm disabled:opacity-50">Prev</button>
        <span className="px-3 py-1 text-sm text-gray-400">Page {page}</span>
        <button onClick={() => setPage(page + 1)} disabled={trades.length < 20}
          className="px-3 py-1 bg-gray-700 rounded text-sm disabled:opacity-50">Next</button>
      </div>
    </div>
  )
}
