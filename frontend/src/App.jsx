import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import StrategyConfig from './pages/StrategyConfig'
import Backtest from './pages/Backtest'
import TradeHistory from './pages/TradeHistory'
import Settings from './pages/Settings'

const navItems = [
  { path: '/', label: 'Dashboard' },
  { path: '/config', label: 'Strategy' },
  { path: '/backtest', label: 'Backtest' },
  { path: '/history', label: 'History' },
  { path: '/settings', label: 'Settings' },
]

export default function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <nav className="bg-gray-800 border-b border-gray-700 px-6 py-3">
        <div className="flex items-center gap-6">
          <span className="text-lg font-bold text-green-400">NiftyAlgo</span>
          {navItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `text-sm px-3 py-1 rounded ${isActive ? 'bg-green-600 text-white' : 'text-gray-300 hover:text-white'}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/config" element={<StrategyConfig />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/history" element={<TradeHistory />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
