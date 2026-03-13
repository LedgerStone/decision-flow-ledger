import { useState, useEffect } from 'react'
import ApprovalFlow from './ApprovalFlow'

export default function QueryDetail({ queryId, api, onClose, onRefresh }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [approver, setApprover] = useState('')
  const [decision, setDecision] = useState('approved')
  const [executor, setExecutor] = useState('')
  const [response, setResponse] = useState(null)

  useEffect(() => {
    load()
  }, [queryId])

  const load = async () => {
    setLoading(true)
    try {
      const d = await api.call(`/queries/${queryId}`)
      setData(d)
    } catch (e) {
      setResponse({ error: e.message })
    }
    setLoading(false)
  }

  const handleApprove = async () => {
    if (!approver) return
    try {
      const r = await api.call('/query/approve', 'POST', {
        query_id: queryId, approver_username: approver, decision
      })
      setResponse(r)
      load()
      onRefresh()
    } catch (e) { setResponse({ error: e.message }) }
  }

  const handleExecute = async () => {
    if (!executor) return
    try {
      const r = await api.call('/query/execute', 'POST', {
        query_id: queryId, executor_username: executor
      })
      setResponse(r)
      load()
      onRefresh()
    } catch (e) { setResponse({ error: e.message }) }
  }

  if (loading) return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="detail-panel" onClick={e => e.stopPropagation()}>
        <div className="loading"><div className="spinner" /></div>
      </div>
    </div>
  )

  if (!data) return null
  const q = data.query
  const isPending = q.status === 'pending'
  const isApproved = q.status === 'approved'

  return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="detail-panel" onClick={e => e.stopPropagation()}>
        <div className="detail-header">
          <div className="card-title">
            Query #{q.id}
            <span className={`badge badge-${q.status}`}>{q.status}</span>
          </div>
          <button className="detail-close" onClick={onClose}>x</button>
        </div>
        <div className="detail-body">
          {/* Info */}
          <div className="detail-section">
            <div className="detail-section-title">Query Info</div>
            <div className="query-sql">{q.query_text}</div>
            <div className="query-reason" style={{ marginTop: 6 }}>Reason: {q.reason}</div>
            <div className="query-meta" style={{ marginTop: 6 }}>Operator: {q.operator} | Created: {q.created_at}</div>
          </div>

          {/* Approval Flow */}
          <div className="detail-section">
            <div className="detail-section-title">Approval Flow</div>
            <ApprovalFlow query={q} approvals={data.approvals} execution={data.execution} />
          </div>

          {/* Actions */}
          {isPending && (
            <div className="detail-section">
              <div className="detail-section-title">Sign Approval</div>
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Approver</label>
                  <input className="form-input" placeholder="bob / carol / dave" value={approver} onChange={e => setApprover(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Decision</label>
                  <select className="form-select" value={decision} onChange={e => setDecision(e.target.value)}>
                    <option value="approved">APPROVE</option>
                    <option value="rejected">REJECT</option>
                  </select>
                </div>
              </div>
              <button className="btn btn-accent" onClick={handleApprove} style={{ width: '100%' }}>Sign Approval</button>
            </div>
          )}

          {isApproved && (
            <div className="detail-section">
              <div className="detail-section-title">Execute Query</div>
              <div className="form-group">
                <label className="form-label">Executor</label>
                <input className="form-input" placeholder="alice / dave" value={executor} onChange={e => setExecutor(e.target.value)} />
              </div>
              <button className="btn btn-amber" onClick={handleExecute} style={{ width: '100%' }}>Execute Query</button>
            </div>
          )}

          {/* Blockchain trail */}
          {data.blockchain_trail?.length > 0 && (
            <div className="detail-section">
              <div className="detail-section-title">Blockchain Trail ({data.blockchain_trail.length} events)</div>
              {data.blockchain_trail.map((e, i) => (
                <div className="block-tx" key={i}>
                  <span className="tx-type">{e.transaction.type}</span>
                  <span>Block #{e.block_index}</span>
                </div>
              ))}
            </div>
          )}

          {/* Response */}
          {response && (
            <div className={`response-box ${response.error ? 'error' : ''}`}>
              {JSON.stringify(response, null, 2)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
