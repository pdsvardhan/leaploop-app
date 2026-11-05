/* Settings — filters (exclude/role types/levels), watch-list & tiers, integrations, watcher health.
   Edits persist via PUT /api/settings and take effect on the next poll. */
import { useState, useEffect } from 'react';
import { Icon } from '../icons.jsx';
import { CompanyLogo, TierBadge, useToast } from '../components.jsx';
import { useSettings, useSaveSettings, useHealth, useUnmute, useIntegrations } from '../api.js';

function SettingsCard({ icon, title, desc, children, tone = 'ok' }) {
  return (
    <div className="card card-pad enter" style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 13, marginBottom: 18 }}>
        <div className={`health-ic ${tone}`} style={{ width: 42, height: 42 }}><Icon name={icon} size={20} /></div>
        <div>
          <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>{title}</h3>
          <p className="muted" style={{ margin: '3px 0 0', fontSize: 13.5 }}>{desc}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function TagInput({ items, color = 'g', onRemove, onAdd, placeholder }) {
  const [v, setV] = useState('');
  const cmap = { g: ['var(--g-100)', 'var(--g-700)', 'var(--g-200)'], r: ['var(--red-bg)', 'var(--red)', '#F3CFC9'] };
  const [bg, fg, bd] = cmap[color];
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
      {items.map((t, i) => (
        <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, background: bg, color: fg, border: `1px solid ${bd}`, padding: '6px 8px 6px 12px', borderRadius: 10, fontSize: 13, fontWeight: 600 }}>
          {t}
          <button onClick={() => onRemove(i)} style={{ display: 'flex', color: fg, opacity: .6 }}><Icon name="x" size={14} /></button>
        </span>
      ))}
      <input value={v} onChange={(e) => setV(e.target.value)} placeholder={placeholder}
        onKeyDown={(e) => { if (e.key === 'Enter' && v.trim()) { onAdd(v.trim()); setV(''); } }}
        style={{ border: '1px dashed var(--line-strong)', borderRadius: 10, padding: '7px 12px', fontSize: 13, outline: 'none', minWidth: 130, flex: '0 1 160px', background: 'transparent' }} />
    </div>
  );
}

function IntegrationRow({ icon, name, status, tone, right }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '12px 0', borderBottom: '1px solid var(--line-2)' }}>
      <div className={`health-ic ${tone}`} style={{ width: 40, height: 40 }}><Icon name={icon} size={20} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 14.5 }}>{name}</div>
        <div className="t3" style={{ fontSize: 12.5, fontWeight: 600 }}>{status}</div>
      </div>
      {right}
    </div>
  );
}

function AddChip({ tier, onAdd }) {
  const [v, setV] = useState('');
  return (
    <input value={v} onChange={(e) => setV(e.target.value)}
      onKeyDown={(e) => { if (e.key === 'Enter' && v.trim()) { onAdd(v.trim()); setV(''); } }}
      placeholder={`+ add to Tier ${tier}`}
      style={{ border: '1px dashed var(--line-strong)', borderRadius: 10, padding: '7px 12px', fontSize: 13, outline: 'none', minWidth: 120, background: 'transparent' }} />
  );
}

export function SettingsScreen() {
  const toast = useToast();
  const { data: settings } = useSettings();
  const { data: health } = useHealth();
  const save = useSaveSettings();
  const unmuteM = useUnmute();          // hook must be above the early return (Rules of Hooks)
  const { data: integ } = useIntegrations();
  const [local, setLocal] = useState(null);

  useEffect(() => { if (settings && !local) setLocal(structuredClone(settings)); }, [settings]); // eslint-disable-line

  if (!local) return <div className="page"><div className="t3" style={{ padding: 40 }}>Loading settings…</div></div>;

  const f = local.filters;
  const setFilters = (patch) => setLocal((s) => ({ ...s, filters: { ...s.filters, ...patch } }));
  const allLevels = f.levels;
  const toggleLevel = (lv) =>
    setFilters({ activeLevels: f.activeLevels.includes(lv) ? f.activeLevels.filter((x) => x !== lv) : [...f.activeLevels, lv] });

  const grouped = { A: [], B: [], C: [] };
  (local.watchlist || []).forEach((w) => { if (grouped[w.tier]) grouped[w.tier].push(w); });
  const addToTier = (tier, co) => setLocal((s) => ({ ...s, watchlist: [...s.watchlist, { co, tier }] }));
  const removeFromWatch = (co) => setLocal((s) => ({ ...s, watchlist: s.watchlist.filter((w) => w.co !== co) }));

  const muted = local.muted || [];
  const unmute = (co) => {
    setLocal((s) => ({ ...s, muted: (s.muted || []).filter((m) => m !== co) }));
    unmuteM.mutate(co, {
      onSuccess: (d) => toast.push(`Unmuted ${co} — ${d.restored} role${d.restored === 1 ? '' : 's'} back in Triage`, { icon: 'check' }),
      onError: (e) => toast.push(e.message, { warn: true }),
    });
  };

  const ageOutDays = local.ageOutDays ?? 30;
  const setAgeOut = (n) => setLocal((s) => ({ ...s, ageOutDays: n }));

  const nameWithCompany = local.nameWithCompany ?? true;
  const setNameWithCompany = (v) => setLocal((s) => ({ ...s, nameWithCompany: v }));

  const doSave = () => save.mutate(
    { filters: local.filters, watchlist: local.watchlist, muted, ageOutDays, nameWithCompany },
    { onSuccess: () => toast.push('Settings saved — applies on the next poll', { icon: 'check' }),
      onError: (e) => toast.push(e.message, { warn: true }) });

  const feeds = health?.feeds || [];

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <div className="page-head">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-sub">Tune the watcher as you go. Changes apply to the next poll.</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-pri" onClick={doSave} disabled={save.isPending}>
            <Icon name="check" size={17} /> {save.isPending ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </div>

      <SettingsCard icon="filter" title="Filters" desc="The watcher only surfaces India PM roles. Tune the exclude list and seniority band here.">
        <div className="field">
          <label>Role types to include</label>
          <TagInput items={f.roleTypes} onAdd={(t) => setFilters({ roleTypes: [...f.roleTypes, t] })} onRemove={(i) => setFilters({ roleTypes: f.roleTypes.filter((_, x) => x !== i) })} placeholder="+ add role type" />
        </div>
        <div className="field">
          <label>Seniority levels (active)</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {allLevels.map((lv) => (
              <button key={lv} className={`fchip ${f.activeLevels.includes(lv) ? 'on' : ''}`} onClick={() => toggleLevel(lv)}>
                {f.activeLevels.includes(lv) && <Icon name="check" size={14} />}{lv}
              </button>
            ))}
          </div>
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Exclude keywords</label>
          <TagInput items={f.exclude} color="r" onAdd={(t) => setFilters({ exclude: [...f.exclude, t] })} onRemove={(i) => setFilters({ exclude: f.exclude.filter((_, x) => x !== i) })} placeholder="+ exclude word" />
          <div className="hint">Roles containing any of these are filtered out before they reach Triage.</div>
        </div>
      </SettingsCard>

      <SettingsCard icon="star" title="Watch-list & tiers" desc="Companies you track, graded by reputation. Tier drives card colour and Telegram priority.">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {['A', 'B', 'C'].map((tier) => (
            <div key={tier}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <TierBadge tier={tier} full />
                <span className="t3" style={{ fontSize: 12.5, fontWeight: 600 }}>{grouped[tier].length} companies</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {grouped[tier].map((w) => (
                  <span key={w.co} className="chip" style={{ paddingLeft: 6, gap: 8 }}>
                    <CompanyLogo co={w.co} size={22} r={6} /> {w.co}
                    <button onClick={() => removeFromWatch(w.co)} style={{ display: 'flex', opacity: .5 }}><Icon name="x" size={13} /></button>
                  </span>
                ))}
                <AddChip tier={tier} onAdd={(c) => addToTier(tier, c)} />
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--line-2)' }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 7 }}>
            <Icon name="mute" size={15} /> Muted companies {muted.length > 0 && <span className="t3">({muted.length})</span>}
          </div>
          {muted.length === 0 ? (
            <div className="hint" style={{ marginTop: 0 }}>None muted. Muting a company in Triage hides its future roles; they'll appear here to unmute.</div>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {muted.map((co) => (
                <span key={co} className="chip" style={{ gap: 9, paddingRight: 6 }}>
                  {co}
                  <button onClick={() => unmute(co)} title="Unmute" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--g-700)', fontWeight: 700, fontSize: 12 }}>
                    <Icon name="refresh" size={13} /> unmute
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </SettingsCard>

      <SettingsCard icon="doc" title="Résumé downloads" desc="Chrome never overwrites a file that already exists, so several downloads in one sitting piled up as “CV (1).pdf”, “CV (2).pdf” — and the ATS uploads whatever the file is called. Adding the company keeps every download uniquely and deliberately named (adr-011).">
        <div style={{ display: 'flex', alignItems: 'center', gap: 13, flexWrap: 'wrap' }}>
          <div className={`toggle ${nameWithCompany ? 'on' : ''}`}
            onClick={() => setNameWithCompany(!nameWithCompany)} />
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600 }}>Add the company to the downloaded filename</div>
            <div className="t3" style={{ fontSize: 12.5, lineHeight: 1.5 }}>
              {nameWithCompany
                ? 'Saves as Sai_Vardhan_Palli_Product_Manager_IIMB_CV_Razorpay.pdf — the master one-pager keeps the plain name.'
                : 'Saves as Sai_Vardhan_Palli_Product_Manager_IIMB_CV.pdf every time, so Chrome will append (1), (2)…'}
            </div>
          </div>
        </div>
      </SettingsCard>

      <SettingsCard icon="clock" title="Queue hygiene" desc="Roles you never decided on pile up in Triage. Anything older than this is auto-skipped so the queue stays a decision surface — nothing you picked, applied or muted is ever touched, and an auto-skip is reversible from the role's undo.">
        <div className="field">
          <label htmlFor="ageout">Auto-skip Triage roles older than</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <input id="ageout" type="number" min="0" max="365" value={ageOutDays}
              onChange={(e) => setAgeOut(Math.max(0, Math.min(365, parseInt(e.target.value, 10) || 0)))}
              style={{ width: 90, border: '1px solid var(--line-strong)', borderRadius: 10, padding: '8px 11px', fontSize: 14, outline: 'none', background: 'transparent' }} />
            <span className="t3" style={{ fontSize: 13 }}>days</span>
            <span className="t3" style={{ fontSize: 12.5 }}>
              {ageOutDays === 0 ? '— age-out disabled; the queue will grow without limit' : `— set 0 to disable`}
            </span>
          </div>
        </div>
      </SettingsCard>

      <SettingsCard icon="link" title="Email automation (Gmail)" desc="LeapLoop reads your Gmail to do two things on its own: mark a role “Applied” when its confirmation email arrives, and pull new roles from your LinkedIn job-alert emails. Read-only — it never sends mail.">
        {/* Item 885: this used to report `configured` — a credential existing — and so said
            "Active" through weeks of dead IMAP. It now reports the last actual outcome. */}
        {(integ?.legs || []).map((leg) => {
          const label = { ok: 'Working', degraded: 'Failing', failed: 'Broken',
                          unknown: 'Not run yet', 'not-configured': 'Off' }[leg.status] || leg.status;
          const tone = leg.status === 'ok' ? 'ok' : leg.status === 'unknown' ? 'ok' : 'amber';
          const detail = leg.status === 'not-configured'
            ? 'Not connected — add GMAIL_USER + GMAIL_APP_PASSWORD in secrets.env'
            : leg.status === 'unknown'
              ? 'Credentials present — status will show after the next poll'
              : leg.status === 'ok'
                ? `Last succeeded ${leg.lastSuccess}`
                : `Last succeeded ${leg.lastSuccess} · last tried ${leg.lastAttempt}${leg.lastError ? ` — ${String(leg.lastError).slice(0, 110)}` : ''}`;
          return (
            <IntegrationRow key={leg.name} icon="gmail" name={leg.label} tone={tone} status={detail}
              right={<span className={`st ${leg.status === 'ok' ? 'applied' : 'saved'}`}>{label}</span>} />
          );
        })}
        {!integ?.legs?.length && (
          <IntegrationRow icon="gmail" name="Gmail / IMAP" tone={integ?.gmail?.configured ? 'ok' : 'amber'}
            status={integ?.gmail?.configured ? 'Connected — no poll recorded yet' : 'Not connected'}
            right={<span className="st saved">{integ?.gmail?.configured ? 'Idle' : 'Off'}</span>} />
        )}
      </SettingsCard>

      <SettingsCard icon="pulse" title="Watcher health" desc="Live status of every source feed." tone={feeds.some((x) => !x.ok) ? 'amber' : 'ok'}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {feeds.length === 0 && <div className="t3" style={{ fontSize: 13 }}>No feed health recorded yet — runs on the next poll.</div>}
          {feeds.map((ff, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '13px 0', borderBottom: i < feeds.length - 1 ? '1px solid var(--line-2)' : 'none' }}>
              <div className={`health-ic ${ff.ok ? 'ok' : 'amber'}`} style={{ width: 36, height: 36, borderRadius: 11 }}>
                <Icon name={ff.kind === 'ATS' ? 'shield' : 'link'} size={17} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{ff.name}</div>
                <div className="t3" style={{ fontSize: 12.5, fontWeight: 600 }}>{ff.ok ? `Last poll ${ff.last} · ${ff.count} fetched` : ff.err}</div>
              </div>
              {ff.ok ? <span className="st applied" style={{ flexShrink: 0 }}>Healthy</span>
                : <span className="st rejected" style={{ flexShrink: 0 }}>Needs attention</span>}
            </div>
          ))}
        </div>
      </SettingsCard>
    </div>
  );
}
