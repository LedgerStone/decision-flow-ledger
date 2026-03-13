import { useState, useEffect } from 'react'

export default function Ledger({ api }) {
  const [entries, setEntries] = useState([])
  const [verification, setVerification] = useState(null)
  const [verifying, setVerifying] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => { load() }, [])

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.call('/ledger')
      setEntries(data.entries || [])
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  const verify = async () => {
    setVerifying(true)
    try {
      const r = await api.call('/ledger/verify')
      setVerification(r)
    } catch (e) {
      setVerification({ valid: false, error: e.message })
    }
    setVerifying(false)
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <div className="card-dot" style={{ background: 'var(--cyan)' }} />
          Immutable Audit Ledger
        </div>
        <div className="card-actions">
          <button className="btn btn-ghost btn-sm" onClick={load}>Refresh</button>
          <button className="btn btn-accent btn-sm" onClick={verify} disabled={verifying}>
            {verifying ? 'Verifying...' : 'Verify Chain'}
          </button>
        </div>
      </div>

      {verification && (
        <div style={{ padding: '16px 20px 0' }}>
          <div className={`verify-banner ${verification.valid ? 'verify-ok' : 'verify-fail'}`}>
            {verification.valid
              ? `Ledger Verified — ${verification.total_entries} entries, chain intact`
              : `Verification Failed — ${verification.error || 'chain broken'}`}
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : (
        <div className="scrollable" style={{ padding: '16px 20px' }}>
          {entries.length === 0 ? (
            <div className="empty"><div className="empty-icon">---</div><div className="empty-text">No ledger entries</div></div>
          ) : entries.map((e, i) => (
            <div className="ledger-entry" key={i}>
              <div className="ledger-row">
                <span className="query-id">Entry #{e.id}</span>
                <span className="ledger-meta">{e.action} — {e.actor}</span>
              </div>
              <div className="ledger-meta">Query #{e.query_id} | {e.timestamp}</div>
              <div className="hash-box">
                <span className="hl">hash: </span>{e.entry_hash?.slice(0, 32)}...
                <br />
                <span className="hl-purple">prev: </span>{e.prev_hash?.slice(0, 32) || 'genesis'}...
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
