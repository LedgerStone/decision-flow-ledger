export default function Stats({ data }) {
  const { queries = [], ledgerCount = 0, bcStats = {}, integrity = '' } = data
  const pending = queries.filter(q => q.status === 'pending').length
  return (
    <div className="stats-row">
      <div className="stat-card green">
        <div className="stat-label">Total Queries</div>
        <div className="stat-value green">{queries.length}</div>
      </div>
      <div className="stat-card blue">
        <div className="stat-label">Ledger Entries</div>
        <div className="stat-value blue">{ledgerCount}</div>
      </div>
      <div className="stat-card purple">
        <div className="stat-label">Blocks</div>
        <div className="stat-value purple">{bcStats.total_blocks || 0}</div>
      </div>
      <div className="stat-card amber">
        <div className="stat-label">Pending</div>
        <div className="stat-value amber">{pending}</div>
      </div>
      <div className="stat-card cyan">
        <div className="stat-label">BC Transactions</div>
        <div className="stat-value cyan">{bcStats.total_transactions || 0}</div>
      </div>
      <div className="stat-card green">
        <div className="stat-label">Integrity</div>
        <div className={`stat-value ${integrity === 'VERIFIED' ? 'green' : 'red'}`}
             style={{ fontSize: '0.9rem', paddingTop: 6 }}>
          {integrity || '--'}
        </div>
      </div>
    </div>
  )
}
