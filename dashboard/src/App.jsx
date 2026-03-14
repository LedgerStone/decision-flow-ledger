import { useState, useEffect, useCallback } from 'react'
import { useApi } from './hooks/useApi'
import Login from './components/Login'
import Header from './components/Header'
import Stats from './components/Stats'
import Queries from './components/Queries'
import QueryDetail from './components/QueryDetail'
import Operations from './components/Operations'
import Ledger from './components/Ledger'
import Blockchain from './components/Blockchain'
import './App.css'

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'operations', label: 'Operations' },
  { id: 'ledger', label: 'Ledger' },
  { id: 'blockchain', label: 'Blockchain' },
]

export default function App() {
  const [auth, setAuth] = useState(null)
  const [tab, setTab] = useState('dashboard')
  const [queries, setQueries] = useState([])
  const [selectedQuery, setSelectedQuery] = useState(null)
  const [statsData, setStatsData] = useState({})
  const [online, setOnline] = useState(false)

  const api = useApi(auth?.url || '', auth?.key || '')

  const loadData = useCallback(async () => {
    if (!auth) return
    try {
      const [q, l, bc, bcs, integrity] = await Promise.all([
        api.call('/queries'),
        api.call('/ledger'),
        api.call('/blockchain'),
        api.call('/blockchain/stats'),
        api.call('/integrity'),
      ])
      setQueries(q.queries || [])
      setStatsData({
        queries: q.queries || [],
        ledgerCount: l.ledger?.length || 0,
        bcStats: bcs,
        integrity: integrity.overall_status || 'UNKNOWN',
      })
      setOnline(true)
    } catch (e) {
      console.error('Load error:', e)
      setOnline(false)
    }
  }, [auth, api])

  useEffect(() => {
    if (auth) loadData()
  }, [auth])

  const handleLogin = (url, key) => {
    setAuth({ url, key })
  }

  const handleLogout = () => {
    setAuth(null)
    setQueries([])
    setStatsData({})
    setTab('dashboard')
  }

  if (!auth) return <Login onLogin={handleLogin} />

  return (
    <div className="app">
      <Header online={online} onLogout={handleLogout} />

      <nav className="nav">
        <div className="nav-inner">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`nav-tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      <main className="main">
        {tab === 'dashboard' && (
          <>
            <Stats data={statsData} />
            <Queries queries={queries} onSelect={setSelectedQuery} api={api} onRefresh={loadData} />
          </>
        )}

        {tab === 'operations' && (
          <Operations api={api} onRefresh={loadData} />
        )}

        {tab === 'ledger' && (
          <Ledger api={api} />
        )}

        {tab === 'blockchain' && (
          <Blockchain api={api} />
        )}
      </main>

      {selectedQuery && (
        <QueryDetail
          queryId={selectedQuery}
          api={api}
          onClose={() => setSelectedQuery(null)}
          onRefresh={loadData}
        />
      )}
    </div>
  )
}
