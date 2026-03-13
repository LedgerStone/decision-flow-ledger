export default function ApprovalFlow({ query, approvals = [], execution }) {
  const status = query.status
  const isRejected = status === 'rejected'

  const steps = [
    {
      label: 'Submitted',
      actor: query.operator,
      done: true,
    },
    {
      label: 'Approval 1',
      actor: approvals[0]?.approver || '---',
      done: approvals.length >= 1,
      isReject: approvals[0]?.decision === 'rejected',
    },
    {
      label: 'Approval 2',
      actor: approvals[1]?.approver || '---',
      done: approvals.length >= 2,
      isReject: approvals[1]?.decision === 'rejected',
      active: approvals.length === 1 && status === 'pending',
    },
    {
      label: 'Executed',
      actor: execution?.executor || '---',
      done: !!execution,
      active: status === 'approved' && !execution,
    },
  ]

  return (
    <div className="flow">
      {steps.map((step, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'flex-start' }}>
          <div className="flow-step">
            <div className={`flow-circle ${step.done ? (step.isReject ? 'rejected' : 'done') : ''} ${step.active ? 'active' : ''}`}>
              {step.done ? (step.isReject ? 'X' : '\u2713') : i + 1}
            </div>
            <div className="flow-label">{step.label}</div>
            <div className="flow-actor">{step.actor}</div>
          </div>
          {i < steps.length - 1 && (
            <div className={`flow-line ${step.done ? 'done' : ''}`} />
          )}
        </div>
      ))}
    </div>
  )
}
