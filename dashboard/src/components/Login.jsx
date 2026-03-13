import { useState } from 'react'

const DEFAULT_URL = 'https://aip-x-api-production.up.railway.app'

export default function Login({ onLogin }) {
  const [apiKey, setApiKey] = useState('')
  const [apiUrl, setApiUrl] = useState(DEFAULT_URL)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!apiKey.trim()) { setError('API key is required'); return }
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${apiUrl.replace(/\/+$/, '')}/operators`, {
        headers: { 'X-Api-Key': apiKey, 'Content-Type': 'application/json' }
      })
      if (res.status === 401) { setError('Invalid API key'); return }
      if (res.status === 422) { setError('API key header not accepted — check server'); return }
      if (!res.ok) { setError(`Server error: ${res.status}`); return }
      onLogin(apiUrl.replace(/\/+$/, ''), apiKey)
    } catch (err) {
      setError(`Connection failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={handleLogin}>
        <div className="login-logo">AIP<span>-X</span></div>
        <div className="login-sub">Accountable Intelligence Platform</div>

        <label className="login-label">API Endpoint</label>
        <input
          className="login-input login-url"
          value={apiUrl}
          onChange={e => setApiUrl(e.target.value)}
          placeholder="https://..."
        />

        <label className="login-label">API Key</label>
        <input
          className="login-input"
          type="password"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          placeholder="Enter your API key"
          autoFocus
        />

        <button className="login-btn" type="submit" disabled={loading}>
          {loading ? 'Connecting...' : 'Connect'}
        </button>

        {error && <div className="login-error">{error}</div>}
      </form>
    </div>
  )
}
