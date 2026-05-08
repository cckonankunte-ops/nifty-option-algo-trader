import { useState, useEffect } from 'react'
import axios from 'axios'

export default function Settings() {
  const [settings, setSettings] = useState(null)
  const [creds, setCreds] = useState({ dhan_client_id: '', dhan_access_token: '' })
  const [verifyStatus, setVerifyStatus] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => { fetchSettings() }, [])

  const fetchSettings = async () => {
    try {
      const res = await axios.get('/api/settings')
      setSettings(res.data)
    } catch (e) { console.error(e) }
  }

  const saveCreds = async () => {
    setSaving(true)
    try {
      await axios.post('/api/settings/broker/credentials', creds)
      fetchSettings()
    } catch (e) { console.error(e) }
    setSaving(false)
  }

  const verifyConnection = async () => {
    setVerifyStatus(null)
    try {
      const res = await axios.post('/api/settings/broker/verify')
      setVerifyStatus(res.data)
    } catch (e) { setVerifyStatus({ connected: false, message: 'Request failed' }) }
  }

  if (!settings) return <div className="text-gray-400">Loading...</div>

  return (
    <div className="max-w-2xl space-y-6">
      <h2 className="text-xl font-semibold">Settings</h2>

      {/* Paper Trading Banner */}
      {settings.paper_mode && (
        <div className="bg-yellow-600/20 border border-yellow-500 text-yellow-300 px-4 py-2 rounded text-sm">
          ⚠️ Paper Trading Mode — No real orders will be placed
        </div>
      )}

      {/* Dhan Broker Connection */}
      <div className="bg-gray-800 rounded p-4 space-y-4">
        <h3 className="text-sm font-medium text-gray-300">Dhan Broker Connection</h3>
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full ${settings.broker_connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm">{settings.broker_connected ? 'Connected' : 'Not Connected'}</span>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-gray-400">Client ID</label>
            <input type="text" value={creds.dhan_client_id}
              onChange={e => setCreds({...creds, dhan_client_id: e.target.value})}
              placeholder="Your Dhan Client ID"
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1" />
          </div>
          <div>
            <label className="text-xs text-gray-400">Access Token</label>
            <input type="password" value={creds.dhan_access_token}
              onChange={e => setCreds({...creds, dhan_access_token: e.target.value})}
              placeholder="Your Dhan Access Token"
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1" />
          </div>
          <p className="text-xs text-gray-500">
            Generate your access token from the Dhan app: My Profile → Access Token
          </p>
        </div>

        <div className="flex gap-3">
          <button onClick={saveCreds} disabled={saving}
            className="bg-green-600 hover:bg-green-700 px-4 py-1.5 rounded text-sm disabled:opacity-50">
            {saving ? 'Saving...' : 'Save Credentials'}
          </button>
          <button onClick={verifyConnection}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-1.5 rounded text-sm">
            Test Connection
          </button>
        </div>

        {verifyStatus && (
          <div className={`text-sm px-3 py-2 rounded ${verifyStatus.connected ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
            {verifyStatus.message}
          </div>
        )}
      </div>

      {/* Trading Mode */}
      <div className="bg-gray-800 rounded p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Trading Mode</h3>
        <span className={`px-3 py-1 rounded text-sm ${
          settings.paper_mode ? 'bg-yellow-600/30 text-yellow-300' : 'bg-green-600/30 text-green-300'
        }`}>
          {settings.paper_mode ? 'Paper Trading (Sandbox)' : 'Live Trading'}
        </span>
        <p className="text-xs text-gray-500">Set DHAN_SANDBOX_MODE=false in .env for real orders.</p>
      </div>

      {/* Trading Window */}
      <div className="bg-gray-800 rounded p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Trading Hours</h3>
        <p className="text-sm">9:45 AM – 3:00 PM IST</p>
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
