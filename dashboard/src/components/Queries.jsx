import { useState } from 'react'

const STATUSES = ['all', 'pending', 'approved', 'rejected', 'executed']

export default function Queries({ queries, onSelect, api, onRefresh }) {
  const [filter, setFilter] = useState('all')
  const filtered = filter === 'all' ? queries : queries.filter(q => q.status === filter)

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <div className="card-dot" style={{ background: 'var(--blue)' }} />
          Query Registry
        </div>
        <button className="btn btn-accent btn-sm" onClick={onRefresh}>Refresh</button>
      </div>
      <div className="filters" style={{ padding: '12px 20px 0' }}>
        {STATUSES.map(s => (
          <button
            key={s}
            className={`filter-chip ${filter === s ? `active ${s}` : ''}`}
            onClick={() => setFilter(s)}
          >
            {s} {s !== 'all' ? `(${queries.filter(q => q.status === s).length})` : `(${queries.length})`}
          </button>
        ))}
      </div>
      <div className="scrollable">
        {filtered.length === 0 ? (
          <div className="empty"><div className="empty-icon">---</div><div className="empty-text">No queries found</div></div>
        ) : filtered.map(q => (
          <div className="query-item" key={q.id}>
            <div className="query-row">
              <span className="query-id">#{q.id} - {q.operator}</span>
              <span className={`badge badge-${q.status}`}>{q.status}</span>
            </div>
            <div className="query-sql">{q.query_text}</div>
            <div className="query-reason">Reason: {q.reason}</div>
            <div className="query-actions">
              <button className="btn btn-blue btn-sm" onClick={() => onSelect(q.id)}>Details</button>
              {q.status === 'pending' && (
                <button className="btn btn-accent btn-sm" onClick={() => onSelect(q.id)}>Approve</button>
              )}
              {q.status === 'approved' && (
                <button className="btn btn-amber btn-sm" onClick={() => onSelect(q.id)}>Execute</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
