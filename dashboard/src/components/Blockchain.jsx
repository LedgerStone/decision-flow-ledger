import { useState, useEffect } from 'react'

export default function Blockchain({ api }) {
  const [blocks, setBlocks] = useState([])
  const [stats, setStats] = useState({})
  const [bcVerify, setBcVerify] = useState(null)
  const [crossVerify, setCrossVerify] = useState(null)
  const [loading, setLoading] = useState(true)
  const [verifying, setVerifying] = useState(false)

  useEffect(() => { load() }, [])

  const load = async () => {
    setLoading(true)
    try {
      const [b, s] = await Promise.all([
        api.call('/blockchain'),
        api.call('/blockchain/stats')
      ])
      setBlocks(b.chain || [])
      setStats(s)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  const verifyBc = async () => {
    setVerifying(true)
    try {
      const r = await api.call('/blockchain/verify')
      setBcVerify(r)
    } catch (e) {
      setBcVerify({ status: 'FAILED', error: e.message })
    }
    setVerifying(false)
  }

  const crossVerifyFn = async () => {
    setVerifying(true)
    try {
      const r = await api.call('/integrity')
      setCrossVerify(r)
    } catch (e) {
      setCrossVerify({ overall_status: 'FAILED', error: e.message })
    }
    setVerifying(false)
  }

  return (
    <>
      {/* Stats */}
      <div className="stats-row" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 16 }}>
        <div className="stat-card purple">
          <div className="stat-label">Total Blocks</div>
          <div className="stat-value purple">{stats.total_blocks || 0}</div>
        </div>
        <div className="stat-card cyan">
          <div className="stat-label">Transactions</div>
          <div className="stat-value cyan">{stats.total_transactions || 0}</div>
        </div>
        <div className="stat-card blue">
          <div className="stat-label">Difficulty</div>
          <div className="stat-value blue">{stats.difficulty || 0}</div>
        </div>
        <div className="stat-card green">
          <div className="stat-label">Chain Valid</div>
          <div className={`stat-value ${bcVerify?.status === 'VERIFIED' ? 'green' : bcVerify ? 'red' : ''}`} style={{ fontSize: '0.9rem', paddingTop: 6 }}>
            {!bcVerify ? '--' : bcVerify.status === 'VERIFIED' ? 'YES' : 'NO'}
          </div>
        </div>
      </div>

      {/* Verification Banners */}
      {bcVerify && (
        <div className={`verify-banner ${bcVerify.status === 'VERIFIED' ? 'verify-ok' : 'verify-fail'}`}>
          {bcVerify.status === 'VERIFIED'
            ? `Blockchain Verified — ${bcVerify.message}`
            : `Blockchain Verification Failed — ${bcVerify.error || bcVerify.message || 'invalid'}`}
        </div>
      )}
      {crossVerify && (
        <div className={`verify-banner ${crossVerify.overall_status === 'VERIFIED' ? 'verify-ok' : 'verify-fail'}`}>
          {crossVerify.overall_status === 'VERIFIED'
            ? `Cross-Verification Passed — ledger & blockchain match`
            : `Integrity: ${crossVerify.overall_status} — ${crossVerify.message || crossVerify.error || ''}`}
        </div>
      )}

      {/* Actions */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div className="card-title">
            <div className="card-dot" style={{ background: 'var(--purple)' }} />
            Blockchain Explorer
          </div>
          <div className="card-actions">
            <button className="btn btn-ghost btn-sm" onClick={load}>Refresh</button>
            <button className="btn btn-purple btn-sm" onClick={verifyBc} disabled={verifying}>Verify Chain</button>
            <button className="btn btn-accent btn-sm" onClick={crossVerifyFn} disabled={verifying}>Cross-Verify</button>
          </div>
        </div>
      </div>

      {/* Blocks */}
      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : blocks.length === 0 ? (
        <div className="empty"><div className="empty-icon">---</div><div className="empty-text">No blocks mined yet</div></div>
      ) : (
        <div className="scrollable">
          {[...blocks].reverse().map((block, i) => (
            <div className="block-card" key={i}>
              <div className="block-header">
                <span className="block-index">Block #{block.index}</span>
                <span className="block-nonce">nonce: {block.nonce}</span>
              </div>
              <div className="hash-box">
                <span className="hl">hash: </span>{block.hash?.slice(0, 48)}...
              </div>
              <div className="hash-box" style={{ marginTop: 4 }}>
                <span className="hl-purple">prev: </span>{block.previous_hash?.slice(0, 48)}...
              </div>
              {block.transactions?.length > 0 && (
                <div className="block-txs">
                  {block.transactions.map((tx, j) => (
                    <div className="block-tx" key={j}>
                      <span className="tx-type">{tx.type}</span>
                      <span>{tx.actor} — Query #{tx.query_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  )
}
