/* Triage queue — fast yes/no/snooze, JD preview, mute company. Honest fit band + transparent gaps.
   Roles with no JD are shown as discovery-only (never as a fit score) and route to Generate. */
import { useState, useMemo } from 'react';
import { Icon } from '../icons.jsx';
import { CompanyLogo, TierBadge, Modal, EmptyState, useToast } from '../components.jsx';
import { useRoles, useDecide, useBulkDecide, useJD } from '../api.js';
import { fitBand, gapLabel } from '../lib.js';

export const PREFILL_KEY = 'leaploop:prefillUrl';

function MetaRow({ r }) {
  return (
    <div className="role-meta">
      <span className="chip"><Icon name="map" size={13} />{r.loc}{r.mode ? ` · ${r.mode}` : ''}</span>
      <span className="chip"><Icon name={r.source === 'ATS' ? 'shield' : 'link'} size={13} />{r.source}</span>
      <span className="chip"><Icon name="clock" size={13} />{r.age} ago</span>
      {r.recent && <span className="flag"><Icon name="flag" size={12} />Applied here recently</span>}
    </div>
  );
}

function FitChip({ r }) {
  const fb = fitBand(r.scored ? r.fit : null);
  if (fb.unscored) {
    // No JD -> nothing was scored. Saying "Safe master" or "0" here would invent a verdict.
    return (
      <span className="badge tier U" title="This role came from an alert with no job description, so nothing was scored against your résumé."
        style={{ display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap' }}>
        <Icon name="link" size={12} /> No JD
      </span>
    );
  }
  return (
    <span className={`badge tier ${fb.tone.toUpperCase()}`} title={`Fit — ${r.fit} resume themes overlap this JD`}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap' }}>
      <Icon name="spark" size={12} /> {fb.label}
    </span>
  );
}

function RoleCard({ r, onAction, onPreview, onMute, selected, onToggle, onTailorFromJd }) {
  const [fly, setFly] = useState(null);
  const act = (type) => {
    setFly(type === 'yes' ? 'fly-yes' : type === 'no' ? 'fly-no' : 'fly-snooze');
    setTimeout(() => onAction(r, type), 460);
  };
  return (
    <div className={`role ${r.tier} collapse ${fly || 'enter'}${selected ? ' selected' : ''}`}>
      <div className="role-top">
        <label className="bulk-check" title="Select for bulk action" onClick={(e) => e.stopPropagation()}>
          <input type="checkbox" checked={selected} onChange={() => onToggle(r.id)} aria-label={`Select ${r.role} at ${r.co}`} />
        </label>
        <CompanyLogo co={r.co} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3>{r.role}</h3>
          <div className="co">
            {r.co}
            <TierBadge tier={r.tier} />
            {r.fresh && <span className="badge" style={{ background: 'var(--g-100)', color: 'var(--g-700)' }}>NEW</span>}
            {r.recruiter && <span className="recruiter" title="Listed by a staffing/recruiter agency, not the employer"><Icon name="flag" size={11} /> recruiter</span>}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <FitChip r={r} />
          <button className="qbtn ghost" style={{ width: 38, height: 38 }} onClick={() => onMute(r)} title="Mute company"><Icon name="mute" size={17} /></button>
        </div>
      </div>
      <MetaRow r={r} />
      <div className="role-actions">
        <button className="qbtn yes" onClick={() => act('yes')} title="Yes — add to Apply"><Icon name="check" /></button>
        <button className="qbtn no" onClick={() => act('no')} title="No — discard"><Icon name="x" /></button>
        <button className="qbtn ghost" onClick={() => act('snooze')} title="Snooze"><Icon name="snooze" /></button>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {r.url && <a className="openlink" href={r.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} title="Open the actual posting">
            <Icon name="external" size={13} /> Open posting
          </a>}
          {r.hasJd ? (
            <button className="btn btn-ghost btn-sm" onClick={() => onPreview(r)} title="Read the job description here">
              <Icon name="eye" size={16} /> Preview JD
            </button>
          ) : (
            <button className="btn btn-ghost btn-sm" onClick={() => onTailorFromJd(r)}
              title="No JD came with this alert. Open Generate with the posting URL filled in, then paste the JD to tailor.">
              <Icon name="doc" size={16} /> Tailor from JD
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h4 style={{ margin: '0 0 9px', fontSize: 13, fontWeight: 700, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>{title}</h4>
      {children}
    </div>
  );
}

function BulkBar({ count, total, onAll, onClear, onBulk, busy }) {
  if (!count) return null;
  return (
    <div className="bulk-bar card card-pad" role="region" aria-label="Bulk actions">
      <strong>{count} selected</strong>
      <button className="btn btn-ghost btn-sm" onClick={onAll} disabled={busy}>Select all {total}</button>
      <button className="btn btn-ghost btn-sm" onClick={onClear} disabled={busy}>Clear</button>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button className="btn btn-ghost btn-sm" onClick={() => onBulk('snooze')} disabled={busy}><Icon name="snooze" size={15} /> Snooze</button>
        <button className="btn btn-ghost btn-sm" onClick={() => onBulk('mute')} disabled={busy}><Icon name="mute" size={15} /> Mute company</button>
        <button className="btn btn-pri btn-sm" onClick={() => onBulk('no')} disabled={busy}><Icon name="x" size={15} /> Discard</button>
      </div>
    </div>
  );
}

function JDModal({ r, onClose, onAction, onTailorFromJd }) {
  const { data: jd, isLoading } = useJD(r.id, true);
  const scored = jd ? jd.scored : r.scored;
  const fitVal = jd?.fit ?? r.fit;
  const fb = fitBand(scored ? fitVal : null);
  const gaps = jd?.gaps || r.gaps || [];
  return (
    <Modal onClose={onClose} max={680}>
      <div className="modal-head">
        <CompanyLogo co={r.co} size={48} />
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 19, fontWeight: 700 }}>{r.role}</h3>
          <div className="co" style={{ marginTop: 5 }}>{r.co} <TierBadge tier={r.tier} full /></div>
        </div>
        <button className="x" onClick={onClose}><Icon name="x" size={18} /></button>
      </div>
      <div className="modal-body">
        <div className="role-meta" style={{ marginTop: 0, marginBottom: 16 }}>
          <span className="chip"><Icon name="map" size={13} />{r.loc}{r.mode ? ` · ${r.mode}` : ''}</span>
          <span className="chip"><Icon name={r.source === 'ATS' ? 'shield' : 'link'} size={13} />{r.source}</span>
          <span className="chip" style={{ color: 'var(--g-700)', borderColor: 'var(--g-200)', background: 'var(--g-050)' }}>
            <Icon name={fb.unscored ? 'link' : 'spark'} size={13} />
            {fb.unscored ? 'No JD — not scored' : `${fb.word} · ${fitVal} theme matches`}
          </span>
        </div>
        {gaps.length > 0 && (
          <div style={{ marginBottom: 16, padding: '11px 13px', borderRadius: 12, background: 'var(--amber-bg)', border: '1px solid #F0DDB0' }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--amber)', marginBottom: 4 }}>Honest gaps this JD triggers</div>
            <div style={{ fontSize: 13, color: 'var(--ink-2)' }}>{gaps.map(gapLabel).join(' · ')} — never auto-added to the resume.</div>
          </div>
        )}
        {r.url && (
          <a className="btn btn-pri btn-sm" href={r.url} target="_blank" rel="noreferrer" style={{ marginBottom: 16 }}>
            <Icon name="external" size={15} /> Open the {r.source === 'LinkedIn' ? 'LinkedIn' : 'role'} posting
          </a>
        )}
        <Section title="Job description">
          {isLoading ? <p className="t3">Loading…</p> :
            jd?.jd_text ? <p style={{ margin: 0, lineHeight: 1.6, color: 'var(--ink-2)', fontSize: 14, whiteSpace: 'pre-wrap' }}>{jd.jd_text.slice(0, 4000)}</p>
              : (
                <div style={{ padding: '16px 18px', borderRadius: 12, background: 'var(--card-2)', border: '1px solid var(--line)', textAlign: 'center' }}>
                  <Icon name="link" size={22} style={{ color: 'var(--ink-3)' }} />
                  <p className="t3" style={{ fontSize: 13.5, margin: '8px 0 10px', lineHeight: 1.5 }}>
                    This role came from a {r.source} alert with no description attached, so nothing was scored
                    against your résumé.<br />Open the posting, then paste the JD to get a tailored PDF.
                  </p>
                  <button className="btn btn-soft btn-sm" onClick={() => { onTailorFromJd(r); onClose(); }}>
                    <Icon name="doc" size={15} /> Tailor from JD
                  </button>
                </div>
              )}
        </Section>
      </div>
      <div className="modal-foot">
        <button className="btn btn-ghost" onClick={() => { onAction(r, 'no'); onClose(); }}><Icon name="x" size={16} /> No</button>
        <button className="btn btn-ghost" onClick={() => { onAction(r, 'snooze'); onClose(); }}><Icon name="snooze" size={16} /> Snooze</button>
        <button className="btn btn-pri" onClick={() => { onAction(r, 'yes'); onClose(); }}><Icon name="check" size={16} /> Yes — add to Apply</button>
      </div>
    </Modal>
  );
}

const parseAge = (a) => { const n = parseInt(a) || 0; return a.includes('m') ? n / 60 : a.includes('h') ? n : n * 24; };
// Unscored roles sort last on Fit rather than colliding with a genuine 0.
const fitKey = (r) => (r.scored ? r.fit : -1);

export function TriageScreen({ query, go }) {
  const toast = useToast();
  const decide = useDecide();
  const bulk = useBulkDecide();
  const { data, isLoading } = useRoles('triage');
  const [tierA, setTierA] = useState(false);
  const [sort, setSort] = useState('tier');
  const [preview, setPreview] = useState(null);
  const [sel, setSel] = useState(() => new Set());
  const queue = data?.roles || [];

  const handle = (r, type) => {
    const decision = type === 'yes' ? 'yes' : type === 'no' ? 'no' : 'snooze';
    decide.mutate({ id: r.id, decision });
    const labels = { yes: 'Added to Apply queue', no: 'Discarded', snooze: 'Snoozed' };
    toast.push(`${r.co} — ${labels[type]}`, {
      icon: type === 'yes' ? 'check' : type === 'snooze' ? 'snooze' : 'x',
      warn: type === 'snooze',
      undo: () => decide.mutate({ id: r.id, decision: 'reset' }),
    });
  };
  const mute = (r) => { decide.mutate({ id: r.id, decision: 'mute' }); toast.push(`Muted ${r.co} — future roles hidden`, { icon: 'mute', warn: true }); };

  // No JD means nothing can be tailored automatically. Hand the posting URL to Generate so the
  // owner pastes the JD once, instead of the queue silently producing an untailored résumé.
  const tailorFromJd = (r) => {
    try { sessionStorage.setItem(PREFILL_KEY, r.url || ''); } catch { /* private mode */ }
    if (go) go('generate');
    else toast.push('Open Generate and paste the JD', { icon: 'doc', warn: true });
  };

  const toggle = (id) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const clearSel = () => setSel(new Set());

  const shown = useMemo(() => {
    let list = [...queue];
    if (tierA) list = list.filter((r) => r.tier === 'A');
    if (query.trim()) {
      const k = query.toLowerCase();
      list = list.filter((r) => r.co.toLowerCase().includes(k) || r.role.toLowerCase().includes(k));
    }
    const rank = { A: 0, B: 1, C: 2, U: 3 };
    if (sort === 'tier') list.sort((a, b) => rank[a.tier] - rank[b.tier] || fitKey(b) - fitKey(a));
    if (sort === 'fit') list.sort((a, b) => fitKey(b) - fitKey(a));
    if (sort === 'age') list.sort((a, b) => parseAge(a.age) - parseAge(b.age));
    return list;
  }, [queue, tierA, query, sort]);

  const runBulk = (decision) => {
    const ids = [...sel];
    if (!ids.length) return;
    bulk.mutate({ ids, decision }, {
      onSuccess: (d) => {
        clearSel();
        const verb = { no: 'Discarded', snooze: 'Snoozed', mute: 'Muted' }[decision] || 'Updated';
        toast.push(`${verb} ${d?.changed ?? ids.length} role${(d?.changed ?? ids.length) === 1 ? '' : 's'}`, {
          icon: decision === 'no' ? 'x' : decision === 'snooze' ? 'snooze' : 'mute',
          warn: decision !== 'no',
          undo: decision === 'no' ? () => bulk.mutate({ ids, decision: 'reset' }) : undefined,
        });
      },
      onError: (e) => toast.push(e.message || 'Bulk action failed', { warn: true }),
    });
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Triage</h1>
          <p className="page-sub">Fast yes / no on fresh roles. {queue.length} waiting · {queue.filter((r) => r.tier === 'A').length} Tier-A.
            {data?.counts?.triage_total > queue.length && <span className="t3"> · {data.counts.triage_total - queue.length} more held back (max 6 / company — clear these and the rest surface)</span>}
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 20 }}>
        <button className={`fchip ${tierA ? 'on' : ''}`} onClick={() => setTierA((v) => !v)}>
          <Icon name="star" size={15} /> Tier-A only
        </button>
        <div className="seg" style={{ marginLeft: 'auto' }}>
          {[['tier', 'Tier'], ['fit', 'Fit'], ['age', 'Newest']].map(([v, l]) => (
            <button key={v} className={sort === v ? 'on' : ''} onClick={() => setSort(v)}>{l}</button>
          ))}
        </div>
      </div>

      <BulkBar count={sel.size} total={shown.length} busy={bulk.isPending}
        onAll={() => setSel(new Set(shown.map((r) => r.id)))} onClear={clearSel} onBulk={runBulk} />

      {isLoading ? <div className="t3" style={{ padding: 40, textAlign: 'center' }}>Loading queue…</div> :
        shown.length === 0 ? (
          <EmptyState icon="check"
            title={queue.length === 0 ? 'Inbox zero' : 'Nothing matches'}
            text={queue.length === 0 ? "You've triaged every fresh role. New ones land here as feeds poll." : 'Try clearing the Tier-A filter or your search.'} />
        ) : (
          <div className="role-grid">
            {shown.map((r) => (
              <RoleCard key={r.id} r={r} onAction={handle} onPreview={setPreview} onMute={mute}
                selected={sel.has(r.id)} onToggle={toggle} onTailorFromJd={tailorFromJd} />
            ))}
          </div>
        )}

      {preview && <JDModal r={preview} onClose={() => setPreview(null)} onAction={handle} onTailorFromJd={tailorFromJd} />}
    </div>
  );
}
