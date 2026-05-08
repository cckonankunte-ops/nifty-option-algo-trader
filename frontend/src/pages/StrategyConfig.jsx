import { useState, useEffect } from 'react'
import axios from 'axios'

export default function StrategyConfig() {
  const [config, setConfig] = useState(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => { fetchConfig() }, [])

  const fetchConfig = async () => {
    try {
      const res = await axios.get('/api/config')
      setConfig(res.data)
    } catch (e) { console.error(e) }
  }

  const save = async () => {
    setSaving(true)
    try {
      await axios.put('/api/config', config)
      setMsg('Config saved')
      setTimeout(() => setMsg(''), 3000)
    } catch (e) { setMsg(e.response?.data?.detail || 'Error saving') }
    setSaving(false)
  }

  const update = (key, value) => setConfig({ ...config, [key]: value })

  if (!config) return <div className="text-gray-400">Loading...</div>

  return (
    <div className="max-w-3xl space-y-6">
      <h2 className="text-xl font-semibold">Strategy Configuration</h2>

      {/* Signal Mode Selection */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Signal Mode</h3>
        <div className="grid grid-cols-2 gap-4">
          <ModeCard
            title="Simple 5-min"
            badge="Recommended for beginners"
            description="EMA crossover + RSI + VWAP on 5-min candles. 3–6 signals/day."
            selected={config.signal_mode === 'SIMPLE_5MIN'}
            onClick={() => update('signal_mode', 'SIMPLE_5MIN')}
          />
          <ModeCard
            title="5-min + 1-min + ADX"
            badge="Higher quality signals"
            description="5-min trend + ADX filter + 1-min confirmation. Fewer but stronger."
            selected={config.signal_mode === 'ADVANCED_5MIN_1MIN_ADX'}
            onClick={() => update('signal_mode', 'ADVANCED_5MIN_1MIN_ADX')}
          />
        </div>
      </div>

      {/* ADX Settings (Advanced mode only) */}
      {config.signal_mode === 'ADVANCED_5MIN_1MIN_ADX' && (
        <div className="bg-gray-800 rounded p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-300">ADX Settings</h3>
          <div className="grid grid-cols-2 gap-4">
            <InputField label="ADX Period" value={config.adx_period} onChange={v => update('adx_period', parseInt(v))} />
            <InputField label="ADX Threshold" value={config.adx_threshold} onChange={v => update('adx_threshold', parseInt(v))} helper="25 = trending, 20 = more trades but noisier" />
          </div>
        </div>
      )}

      {/* Trading Window Info */}
      <div className="bg-blue-900/20 border border-blue-700 rounded p-3 text-sm text-blue-300">
        Trading window: 9:45 AM – 3:00 PM IST. First 30 minutes after open skipped to avoid volatility.
      </div>

      {/* EMA Settings */}
      <div className="bg-gray-800 rounded p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">EMA Settings</h3>
        <div className="grid grid-cols-2 gap-4">
          <InputField label="Fast Period" value={config.ema_fast} onChange={v => update('ema_fast', parseInt(v))} />
          <InputField label="Slow Period" value={config.ema_slow} onChange={v => update('ema_slow', parseInt(v))} />
        </div>
      </div>

      {/* RSI Settings */}
      <div className="bg-gray-800 rounded p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">RSI Settings</h3>
        <div className="grid grid-cols-3 gap-4">
          <InputField label="Period" value={config.rsi_period} onChange={v => update('rsi_period', parseInt(v))} />
          <InputField label="Upper Threshold" value={config.rsi_upper} onChange={v => update('rsi_upper', parseInt(v))} />
          <InputField label="Lower Threshold" value={config.rsi_lower} onChange={v => update('rsi_lower', parseInt(v))} />
        </div>
      </div>

      {/* Risk Settings */}
      <div className="bg-gray-800 rounded p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Risk Settings</h3>
        <div className="grid grid-cols-2 gap-4">
          <InputField label="Stop Loss %" value={config.sl_percent} onChange={v => update('sl_percent', parseFloat(v))} />
          <InputField label="Trailing SL Trigger %" value={config.trailing_sl_trigger} onChange={v => update('trailing_sl_trigger', parseFloat(v))} />
          <InputField label="Trailing SL Trail %" value={config.trailing_sl_trail} onChange={v => update('trailing_sl_trail', parseFloat(v))} />
          <InputField label="Daily Loss Cap %" value={config.daily_loss_cap_percent} onChange={v => update('daily_loss_cap_percent', parseFloat(v))} />
          <InputField label="Fund Per Trade %" value={config.fund_per_trade_percent} onChange={v => update('fund_per_trade_percent', parseFloat(v))} />
        </div>
      </div>

      {/* Save */}
      <div className="flex items-center gap-4">
        <button onClick={save} disabled={saving} className="bg-green-600 hover:bg-green-700 px-6 py-2 rounded font-medium disabled:opacity-50">
          {saving ? 'Saving...' : 'Save Config'}
        </button>
        {msg && <span className="text-green-400 text-sm">{msg}</span>}
      </div>
    </div>
  )
}

function ModeCard({ title, badge, description, selected, onClick }) {
  return (
    <div
      onClick={onClick}
      className={`cursor-pointer rounded p-4 border-2 transition ${
        selected ? 'border-green-500 bg-green-900/20' : 'border-gray-600 bg-gray-800 hover:border-gray-500'
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="font-medium">{title}</span>
        <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">{badge}</span>
      </div>
      <p className="text-sm text-gray-400">{description}</p>
    </div>
  )
}

function InputField({ label, value, onChange, helper }) {
  return (
    <div>
      <label className="text-xs text-gray-400">{label}</label>
      <input
        type="number"
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm mt-1"
      />
      {helper && <p className="text-xs text-gray-500 mt-1">{helper}</p>}
    </div>
  )
}
