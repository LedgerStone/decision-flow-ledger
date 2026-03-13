import { useState } from 'react'

export default function Operations({ api, onRefresh }) {
  const [operator, setOperator] = useState('')
  const [queryText, setQueryText] = useState('')
  const [reason, setReason] = useState('')
  const [response, setResponse] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!operator || !queryText || !reason) return
    try {
      const r = await api.call('/query/submit', 'POST', {
        operator_username: operator,
        query_text: queryText,
        reason
      })
      setResponse(r)
      setOperator('')
      setQueryText('')
      setReason('')
      onRefresh()
    } catch (err) {
      setResponse({ error: err.message })
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <div className="card-dot" style={{ background: 'var(--amber)' }} />
          Submit New Query
        </div>
      </div>
      <div className="card-body">
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Operator</label>
              <input className="form-input" placeholder="alice / eve" value={operator} onChange={e => setOperator(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Reason</label>
              <input className="form-input" placeholder="Why is this query needed?" value={reason} onChange={e => setReason(e.target.value)} />
            </div>
            <div className="form-group full">
              <label className="form-label">SQL Query</label>
              <input className="form-input" placeholder="SELECT * FROM ..." value={queryText} onChange={e => setQueryText(e.target.value)} />
            </div>
          </div>
          <button className="btn btn-accent" type="submit" style={{ width: '100%', marginTop: 4 }}>Submit Query</button>
        </form>
        {response && (
          <div className={`response-box ${response.error ? 'error' : ''}`}>
            {JSON.stringify(response, null, 2)}
          </div>
        )}
      </div>
    </div>
  )
}
