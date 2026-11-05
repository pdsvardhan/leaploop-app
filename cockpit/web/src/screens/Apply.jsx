/* Apply queue — real tailored-PDF preview, swap-variant, copy referral (locked template), applied toggle. */
import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Icon } from '../icons.jsx';
import { CompanyLogo, TierBadge, EmptyState, useToast } from '../components.jsx';
import { useRoles, useTailor, useApplied, useDecide, pdfRoleUrl } from '../api.js';
import { referralDraft } from '../lib.js';
import { ResumeEditor } from '../ResumeEditor.jsx';

function ApplyCard({ r }) {
  const toast = useToast();
  const tailor = useTailor();
  const applied = useApplied();
  const decide = useDecide();
  const [swapOpen, setSwapOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const regen = tailor.isPending;
  const pdfDisabled = !r.pdfReady || regen;

  const reject = () => {
    decide.mutate({ id: r.id, decision: 'no' });
    toast.push(`Removed · ${r.co}`, { icon: 'x', warn: true,
      undo: () => decide.mutate({ id: r.id, decision: 'yes' }) });
  };

  const doRegen = (v) => {
    setSwapOpen(false);
    tailor.mutate({ id: r.id, variant: v || r.variant }, {
      onSuccess: (d) => toast.push(`Resume regenerated · ${d.variant}`, { icon: 'refresh' }),
      onError: (e) => toast.push(`Tailoring failed: ${e.message}`, { warn: true }),
    });
  };
  const copyReferral = () => {
    const text = referralDraft('', r.role, r.co);
    navigator.clipboard?.writeText(text).catch(() => {});
    setCopied(true); setTimeout(() => setCopied(false), 1800);
    toast.push('Referral draft copied — add the contact name', { icon: 'copy' });
  };
  const toggleApplied = () => {
    const nv = !r.applied;
    applied.mutate({ id: r.id, applied: nv });
    toast.push(nv ? `Marked applied · ${r.co}` : `Applied undone · ${r.co}`, { icon: nv ? 'check' : 'refresh' });
  };

  return (
    <div className={`role ${r.tier}`}>
      <div className="role-top">
        <CompanyLogo co={r.co} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3>{r.role}</h3>
          <div className="co">{r.co} <TierBadge tier={r.tier} />{r.applied && <span className="st applied">Applied</span>}</div>
        </div>
      </div>
      <div className="role-meta">
        <span className="chip"><Icon name="map" size={13} />{r.loc}{r.mode ? ` · ${r.mode}` : ''}</span>
        <span className="chip"><Icon name={r.source === 'ATS' ? 'shield' : 'link'} size={13} />{r.source}</span>
        <span className="chip" title="Tailored resume variant"><Icon name="doc" size={13} />{r.variant || 'Not tailored yet'}</span>
        {!r.pdfReady && <span className="chip" style={{ color: 'var(--g-700)' }}><Icon name="refresh" size={13} style={{ animation: 'spin 1s linear infinite' }} /> Tailoring…</span>}
      </div>

      <div style={{ marginTop: 16, position: 'relative' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink-3)', marginBottom: 7 }}>RESUME VARIANT</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-soft btn-sm" onClick={() => setSwapOpen((v) => !v)} disabled={regen}>
            <Icon name="doc" size={15} /> {r.variant || 'Choose a variant'} <Icon name="chevdown" size={14} />
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => doRegen(null)} disabled={regen}>
            <Icon name="refresh" size={15} style={regen ? { animation: 'spin 1s linear infinite' } : {}} /> {regen ? 'Generating…' : 'Regenerate'}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => setEditOpen(true)} disabled={regen} title="Tweak keywords or edit the LaTeX">
            <Icon name="edit" size={15} /> Edit
          </button>
        </div>
        {swapOpen && (
          <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 6, background: 'var(--app)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--sh-lg)', padding: 6, zIndex: 10, minWidth: 220 }}>
            {(r.variants || []).map((v) => (
              <button key={v} onClick={() => doRegen(v)} style={{ display: 'flex', alignItems: 'center', gap: 9, width: '100%', textAlign: 'left', padding: '9px 11px', borderRadius: 9, fontSize: 13.5, fontWeight: 600, color: v === r.variant ? 'var(--g-700)' : 'var(--ink-2)', background: v === r.variant ? 'var(--g-050)' : 'transparent' }}>
                <Icon name={v === r.variant ? 'check' : 'doc'} size={15} /> {v}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Apply actions */}
      <div style={{ display: 'flex', gap: 9, marginTop: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <a className="btn btn-pri" href={r.url || '#'} target="_blank" rel="noreferrer">
          <Icon name="external" size={16} /> Apply on {r.source}
        </a>
        <button className="btn btn-ghost" onClick={copyReferral}>
          <Icon name={copied ? 'check' : 'copy'} size={16} /> {copied ? 'Copied' : 'Copy referral'}
        </button>
        <button className="btn btn-danger btn-sm" onClick={reject} title="Not interested — remove from Apply">
          <Icon name="x" size={15} /> Not interested
        </button>
      </div>

      {/* Résumé: the three buttons — Preview CV · Download PDF · Applied */}
      <div style={{ display: 'flex', gap: 9, marginTop: 12, flexWrap: 'wrap', alignItems: 'center', paddingTop: 12, borderTop: '1px solid var(--line-2)' }}>
        <a className="btn btn-soft btn-sm" href={pdfRoleUrl(r.id)} target="_blank" rel="noreferrer"
          style={{ pointerEvents: pdfDisabled ? 'none' : 'auto', opacity: pdfDisabled ? .5 : 1 }} title={pdfDisabled ? 'Tailoring…' : 'Open the tailored résumé'}>
          <Icon name="eye" size={15} /> Preview CV
        </a>
        <a className="btn btn-soft btn-sm" href={pdfRoleUrl(r.id)} download
          style={{ pointerEvents: pdfDisabled ? 'none' : 'auto', opacity: pdfDisabled ? .5 : 1 }} title={pdfDisabled ? 'Tailoring…' : 'Download the tailored résumé'}>
          <Icon name="download" size={15} /> Download PDF
        </a>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginLeft: 'auto' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-2)' }}>Applied</span>
          <div className={`toggle ${r.applied ? 'on' : ''}`} onClick={toggleApplied} />
        </div>
      </div>

      {editOpen && <ResumeEditor roleId={r.id} onClose={() => setEditOpen(false)} />}
    </div>
  );
}

export function ApplyScreen() {
  const { data, isLoading } = useRoles('apply');
  const qc = useQueryClient();
  const roles = (data?.roles || []).filter((r) => !r.applied || r.pdfReady);
  const pending = roles.some((r) => !r.pdfReady);

  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => qc.invalidateQueries({ queryKey: ['roles', 'apply'] }), 3000);
    return () => clearInterval(t);
  }, [pending, qc]);

  const notApplied = roles.filter((r) => !r.applied).length;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Apply</h1>
          <p className="page-sub">{roles.length} ready · {notApplied} not yet applied. Tailored resume waiting on each.</p>
        </div>
      </div>
      {isLoading ? <div className="t3" style={{ padding: 40, textAlign: 'center' }}>Loading…</div> :
        roles.length === 0 ? (
          <EmptyState icon="apply" title="Nothing to apply to yet" text="Say Yes to roles in Triage and they'll show up here with a tailored resume ready to go." />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {roles.map((r) => <ApplyCard key={r.id} r={r} />)}
          </div>
        )}
    </div>
  );
}
