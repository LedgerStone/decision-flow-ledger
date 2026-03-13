export default function Header({ online, onLogout }) {
  return (
    <header className="header">
      <div className="header-inner">
        <div className="header-left">
          <div className="logo">AIP<span>-X</span></div>
          <span className="badge-mvp">MVP</span>
        </div>
        <div className="header-right">
          <div className={`status-dot ${online ? '' : 'offline'}`} />
          <span className="status-text">{online ? 'CONNECTED' : 'OFFLINE'}</span>
          <button className="logout-btn" onClick={onLogout}>Logout</button>
        </div>
      </div>
    </header>
  )
}
