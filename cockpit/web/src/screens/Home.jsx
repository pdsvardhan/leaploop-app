/* Home / Inbox — two action tiles, watcher health, top Tier-A, quick generate. */
import { useState, useEffect } from 'react';
import { Icon } from '../icons.jsx';
import { CompanyLogo, HealthStrip, LogoMark, TierBadge } from '../components.jsx';
import { useMe, useRoles } from '../api.js';

function Counter({ value }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    let raf, start, done = false;
    const dur = 700;
    const step = (t) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / dur);
      setN(Math.round((1 - Math.pow(1 - p, 3)) * value));
      if (p < 1) raf = requestAnimationFrame(step); else done = true;
    };
    raf = requestAnimationFrame(step);
    const fb = setTimeout(() => { if (!done) setN(value); }, dur + 250);
    return () => { cancelAnimationFrame(raf); clearTimeout(fb); };
  }, [value]);
  return <span>{n}</span>;
}

function ActionTile({ kind, count, label, sub, onClick, icon, noCount }) {
  return (
    <div className={`atile ${kind}`} onClick={onClick}>
      <div className="deco" />
      <div className="arrow"><Icon name="arrow" size={19} /></div>
      <div className="lbl"><Icon name={icon} size={20} /> {label}</div>
      <div className="big">{noCount ? <Icon name={icon} size={38} style={{ opacity: .9 }} /> : <Counter value={count} />}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}

export function HomeScreen({ go }) {
  const { data: me } = useMe();
  const { data: triage } = useRoles('triage');
  const { data: applyData } = useRoles('apply');
  const roles = triage?.roles || [];
  const counts = triage?.counts || { triage: 0, apply: 0 };
  const topA = roles.filter((r) => r.tier === 'A').slice(0, 3);
  const tierA = roles.filter((r) => r.tier === 'A').length;
  // Apply-queue mirror of the Apply screen's filter; not-yet-applied first, then ready-but-applied.
  const applyRoles = (applyData?.roles || []).filter((r) => !r.applied || r.pdfReady);
  const applyPending = applyRoles.filter((r) => !r.applied);
  const applyTop = [...applyPending, ...applyRoles.filter((r) => r.applied)].slice(0, 4);
  const hour = new Date().getHours();
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const first = (me?.name || 'there').split(' ')[0];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">{greet}, {first}</h1>
          <p className="page-sub">Two quick queues today. Clear them and you're done.</p>
        </div>
      </div>

      <div className="tiles enter">
        <ActionTile kind="hero" icon="triage" count={counts.triage}
          label="Triage" sub={`${tierA} Tier-A · yes / no`} onClick={() => go('triage')} />
        <ActionTile kind="hero2" icon="apply" count={counts.apply}
          label="Apply" sub="resumes ready to send" onClick={() => go('apply')} />
        <ActionTile kind="flat" icon="tracker" count={counts.applied || 0}
          label="Tracker" sub="applications logged" onClick={() => go('tracker')} />
        <ActionTile kind="flat" icon="pdf" noCount
          label="Generate" sub="paste a JD → tailored PDF" onClick={() => go('generate')} />
      </div>

      <div style={{ marginTop: 22 }}><HealthStrip go={go} /></div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18, marginTop: 22 }} className="home-split">
        <div className="card card-pad enter">
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>Top Tier-A in your queue</h3>
            <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }} onClick={() => go('triage')}>Open Triage <Icon name="chevright" size={14} /></button>
          </div>
          {topA.length === 0 ? (
            <div className="t3" style={{ fontSize: 14, padding: '20px 0', textAlign: 'center' }}>No Tier-A roles waiting — nicely done.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {topA.map((r) => (
                  <div key={r.id} onClick={() => go('triage')} style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '11px 13px', border: '1px solid var(--line)', borderRadius: 14, cursor: 'pointer', borderLeft: '4px solid var(--tier-a)' }} className="hov-row">
                    <CompanyLogo co={r.co} size={38} r={11} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: 14.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.role}</div>
                      <div className="t3" style={{ fontSize: 12.5, fontWeight: 600 }}>{r.co} · {r.loc} · {r.age} ago</div>
                    </div>
                    <TierBadge tier={r.tier} />
                  </div>
              ))}
            </div>
          )}
        </div>

        <div className="card card-pad enter" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>Apply queue</h3>
            {applyPending.length > 0 && <span className="t3" style={{ fontSize: 12.5, fontWeight: 600, marginLeft: 8 }}>{applyPending.length} ready to send</span>}
            <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }} onClick={() => go('apply')}>Open Apply <Icon name="chevright" size={14} /></button>
          </div>
          {applyTop.length === 0 ? (
            <div className="t3" style={{ fontSize: 14, padding: '20px 0', textAlign: 'center' }}>Nothing to apply to yet — say Yes in Triage.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {applyTop.map((r) => (
                  <div key={r.id} onClick={() => go('apply')} style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '11px 13px', border: '1px solid var(--line)', borderRadius: 14, cursor: 'pointer' }} className="hov-row">
                    <CompanyLogo co={r.co} size={38} r={11} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: 14.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.role}</div>
                      <div className="t3" style={{ fontSize: 12.5, fontWeight: 600 }}>{r.co} · {r.loc}</div>
                    </div>
                    {r.applied
                      ? <span className="st applied">Applied</span>
                      : r.pdfReady
                        ? <span className="st applied">Ready</span>
                        : <span className="st saved">Tailoring…</span>}
                  </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* Authentik SSO splash — shown only if the app is reached without forward-auth (dev/standalone). */
export function LoginScreen() {
  return (
    <div className="login">
      <div className="orb" style={{ width: 320, height: 320, top: '-80px', left: '-60px' }} />
      <div className="orb" style={{ width: 220, height: 220, bottom: '-40px', right: '8%' }} />
      <div className="login-card enter">
        <div className="login-mark"><LogoMark s={30} /></div>
        <h1 style={{ margin: '0 0 4px', fontSize: 26, fontWeight: 800, letterSpacing: '-.02em' }}>LeapLoop</h1>
        <p style={{ margin: '0 0 26px', color: 'var(--ink-2)', fontSize: 14 }}>Your private job-hunt cockpit.</p>
        <a className="btn btn-pri btn-block btn-lg" href="/"><Icon name="shield" size={18} /> Continue with Authentik SSO</a>
        <div style={{ marginTop: 18, fontSize: 12, color: 'var(--ink-3)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <Icon name="shield" size={13} /> Single-user · end-to-end private
        </div>
      </div>
    </div>
  );
}
