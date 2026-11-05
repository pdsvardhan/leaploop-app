/* LeapLoop — shared components (ported from the reference, wired to the API). */
import { createContext, useContext, useState, useEffect, useCallback, Component } from 'react';
import { Icon } from './icons.jsx';
import { companyHue, shade, logoText } from './lib.js';
import { useMe, useHealth } from './api.js';

export function LogoMark({ s = 24 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#fff"
      strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 19.5V8.5" />
      <path d="M7.7 12.8 12 8.5l4.3 4.3" />
      <path d="M5 16.5a7.2 7.2 0 0 0 14 0" />
    </svg>
  );
}

export function CompanyLogo({ co, size = 44, r = 12 }) {
  const hue = companyHue(co);
  return (
    <div className="logo" style={{
      width: size, height: size, borderRadius: r,
      background: `linear-gradient(150deg, ${hue}, ${shade(hue, -22)})`,
      fontSize: size * 0.38,
    }}>{logoText(co)}</div>
  );
}

const TIER_LETTER = { A: 'A', B: 'B', C: 'C', U: '?' };
export const TIER_LABEL = { A: 'Tier A', B: 'Tier B', C: 'Tier C', U: 'Unverified' };
export function TierBadge({ tier, full }) {
  return <span className={`badge tier ${tier}`}>{full ? TIER_LABEL[tier] : `Tier ${TIER_LETTER[tier]}`}</span>;
}

const NAV = [
  { id: 'home', label: 'Home', icon: 'home' },
  { id: 'triage', label: 'Triage', icon: 'triage' },
  { id: 'apply', label: 'Apply', icon: 'apply' },
  { id: 'tracker', label: 'Tracker', icon: 'tracker' },
  { id: 'generate', label: 'Generate PDF', icon: 'pdf' },
];

export function Sidebar({ route, go, counts }) {
  const item = (n) => (
    <div key={n.id} className={`sb-item ${route === n.id ? 'on' : ''}`} onClick={() => go(n.id)}>
      <Icon name={n.icon} />
      <span>{n.label}</span>
      {n.id === 'triage' && counts.triage > 0 && <span className="sb-badge">{counts.triage}</span>}
      {n.id === 'apply' && counts.apply > 0 && <span className="sb-badge">{counts.apply}</span>}
    </div>
  );
  return (
    <aside className="sb">
      <div className="sb-logo">
        <div className="sb-mark"><LogoMark /></div>
        <span className="sb-word">LeapLoop</span>
      </div>
      <div className="sb-group">Queues</div>
      {NAV.map(item)}
      <div className="sb-group">General</div>
      <div className={`sb-item ${route === 'settings' ? 'on' : ''}`} onClick={() => go('settings')}>
        <Icon name="settings" /><span>Settings</span>
        {counts.broken > 0 && <span className="sb-badge amber">!</span>}
      </div>
    </aside>
  );
}

export function Topbar({ onSearch, query, showSearch = true }) {
  const { data: u } = useMe();
  return (
    <div className="topbar">
      {showSearch && (
        <div className="search">
          <Icon name="search" size={18} />
          <input placeholder="Search roles, companies, the tracker…" value={query}
            onChange={(e) => onSearch(e.target.value)} />
        </div>
      )}
      <div style={{ flex: 1 }} />
      <div className="tb-user">
        <div className="tb-avatar">{u?.initials || 'SV'}</div>
        <div>
          <div className="tb-name">{u?.name || 'LeapLoop'}</div>
          <div className="tb-mail">{u?.email || ''}</div>
        </div>
      </div>
    </div>
  );
}

export function MobileTop() {
  return (
    <div className="mtop">
      <div className="sb-mark"><LogoMark s={18} /></div>
      <span className="sb-word">LeapLoop</span>
      <div className="spacer" />
    </div>
  );
}

export function BottomNav({ route, go, counts }) {
  const items = [
    { id: 'home', label: 'Home', icon: 'home' },
    { id: 'triage', label: 'Triage', icon: 'triage', badge: counts.triage },
    { id: 'apply', label: 'Apply', icon: 'apply', badge: counts.apply },
    { id: 'tracker', label: 'Tracker', icon: 'tracker' },
    { id: 'settings', label: 'Settings', icon: 'settings' },
  ];
  return (
    <nav className="botnav">
      {items.map((i) => (
        <button key={i.id} className={route === i.id ? 'on' : ''} onClick={() => go(i.id)}>
          <Icon name={i.icon} size={23} fill={route === i.id ? 'rgba(27,107,65,.12)' : 'none'} />
          <span>{i.label}</span>
          {i.badge > 0 && <span className="nbadge">{i.badge}</span>}
        </button>
      ))}
    </nav>
  );
}

export function HealthStrip({ go }) {
  const { data } = useHealth();
  const broken = data?.brokenFeeds || 0;
  return (
    <div className="health enter">
      <div className="health-cell">
        <div className="health-ic ok"><Icon name="refresh" size={19} /></div>
        <div>
          <div className="health-k">Last poll</div>
          <div className="health-v">{data?.lastPoll || '—'} <span className="pulse" style={{ color: 'var(--g-500)', fontSize: 13 }}>●</span></div>
        </div>
      </div>
      <div className="health-cell">
        <div className="health-ic blue"><Icon name="inbox" size={19} /></div>
        <div>
          <div className="health-k">New today</div>
          <div className="health-v">{data?.newToday ?? 0} roles sourced</div>
        </div>
      </div>
      <div className="health-cell" style={{ cursor: broken ? 'pointer' : 'default' }} onClick={() => broken && go('settings')}>
        <div className={`health-ic ${broken ? 'amber' : 'ok'}`}>
          <Icon name={broken ? 'bolt' : 'check'} size={19} />
        </div>
        <div style={{ flex: 1 }}>
          <div className="health-k">Watcher health</div>
          <div className="health-v" style={{ color: broken ? 'var(--amber)' : 'inherit' }}>
            {broken ? `${broken} feed needs attention` : 'All feeds healthy'}
          </div>
        </div>
        {broken > 0 && <Icon name="chevright" size={18} style={{ color: 'var(--amber)' }} />}
      </div>
    </div>
  );
}

export function Modal({ children, onClose, max = 600 }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [onClose]);
  return (
    <div className="scrim" onClick={onClose}>
      <div className="modal" style={{ maxWidth: max }} onClick={(e) => e.stopPropagation()}>{children}</div>
    </div>
  );
}

const ToastCtx = createContext(null);
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((msg, opts = {}) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, msg, ...opts }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), opts.duration || 3200);
    return id;
  }, []);
  const remove = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.warn ? 'warn' : ''}`}>
            <span className="tic"><Icon name={t.warn ? 'snooze' : (t.icon || 'check')} size={15} /></span>
            <span>{t.msg}</span>
            {t.undo && <span className="undo" onClick={() => { t.undo(); remove(t.id); }}>Undo</span>}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

export function Segmented({ options, value, onChange }) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o.v} className={value === o.v ? 'on' : ''} onClick={() => onChange(o.v)}>{o.label}</button>
      ))}
    </div>
  );
}

export function EmptyState({ icon, title, text, action }) {
  return (
    <div className="empty enter">
      <div className="empty-ic"><Icon name={icon} size={36} /></div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}

/* Catches a screen-level render error so one broken screen can't blank the whole cockpit. */
export class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { err: null }; }
  static getDerivedStateFromError(err) { return { err }; }
  componentDidCatch(err, info) { console.error('Screen crashed:', err, info); }
  render() {
    if (this.state.err) {
      return (
        <div className="empty enter" style={{ padding: 40 }}>
          <div className="empty-ic"><Icon name="bolt" size={34} /></div>
          <h3>This screen hit an error</h3>
          <p style={{ maxWidth: 420 }}>{String(this.state.err.message || this.state.err).slice(0, 200)}</p>
          <button className="btn btn-pri" style={{ marginTop: 14 }} onClick={() => this.setState({ err: null })}>Try again</button>
        </div>
      );
    }
    return this.props.children;
  }
}
