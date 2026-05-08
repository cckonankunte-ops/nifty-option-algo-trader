import { useState, useEffect } from 'react'
import axios from 'axios'

export default function Settings() {
  const [settings, setSettings] = useState(null)

  useEffect(() => { fetchSettings() }, [])

  const fetchSettings = async () => {
    try {
      const res = await axios.get('/api/settings')
      setSettings(res.data)
    } catch (e) { console.error(e) }
  }

  if (!settings) return <div className="text-gray-400">Loading...</div>

  return (
    <div className="max-w-2xl space-y-6">
      <h2 className="text-xl font-semibold">Settings</h2>

      {/* Broker Connection */}
      <div className="bg-gray-800 rounded p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Broker Connection</h3>
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full ${settings.broker_connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm">{settings.broker_connected ? 'Connected' : 'Not Connected'}</span>
        </div>
        <p className="text-xs text-gray-500">
          Configure FYERS_APP_ID and FYERS_ACCESS_TOKEN in your .env file.
        </p>
      </div>

      {/* Trading Mode */}
      <div className="bg-gray-800 rounded p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Trading Mode</h3>
        <span className={`px-3 py-1 rounded text-sm ${
          settings.trading_mode === 'paper' ? 'bg-yellow-600/30 text-yellow-300' : 'bg-green-600/30 text-green-300'
        }`}>
          {settings.trading_mode === 'paper' ? 'Paper Trading' : 'Live Trading'}
        </span>
        <p className="text-xs text-gray-500">Set TRADING_MODE=live in .env for real orders.</p>
      </div>

      {/* Trading Window */}
      <div className="bg-gray-800 rounded p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Trading Hours</h3>
        <p className="text-sm">
          {settings.trading_window?.start || '09:45'} AM – {settings.trading_window?.end || '15:00'} PM IST
        </p>
        <p className="text-xs text-gray-500">Square-off at 3:15 PM. Market close at 3:30 PM.</p>
      </div>

      {/* Environment */}
      <div className="bg-gray-800 rounded p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Environment</h3>
        <p className="text-sm">{settings.environment}</p>
      </div>
    </div>
  )
}
