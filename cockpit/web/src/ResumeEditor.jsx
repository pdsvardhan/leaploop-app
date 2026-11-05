/* Per-JD résumé editor (item 307). Two modes, both deterministic (no LLM):
   - Quick edit: chip/field tweaks over the flex macros (descriptor, 5th bullet, skill/domain tags).
   - Raw .tex: edit the assembled LaTeX directly; a compile error shows inline and the last good PDF stays.
   Works for an Apply-queue role (roleId) or a manually generated PDF (token). */
import { useState, useEffect } from 'react';
import { Icon } from './icons.jsx';
import { Modal, useToast } from './components.jsx';
import { useRoleEdit, useRecompileRole, useGenerateEdit, useRecompileGenerated } from './api.js';

const cleanBullet = (t) => (t || '').replace(/\\item\s*/, '').replace(/\\[a-zA-Z]+/g, '').replace(/[{}]/g, '').trim();

function Field({ label, value, onChange, placeholder, disabled }) {
  return (
    <div className="field">
      <label>{label}</label>
      <input className="inp" value={value || ''} placeholder={placeholder} disabled={disabled}
        onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

export function ResumeEditor({ roleId, token, onClose, onSaved }) {
  const toast = useToast();
  const isRole = !!roleId;
  // Both hooks are always called (Rules of Hooks); `enabled` decides which actually fetches.
  const roleEdit = useRoleEdit(roleId, isRole);
  const genEdit = useGenerateEdit(token, !isRole);
  const edit = isRole ? roleEdit : genEdit;
  const recompRole = useRecompileRole();
  const recompGen = useRecompileGenerated();

  const [tab, setTab] = useState('chips');
  const [ov, setOv] = useState(null);
  const [tex, setTex] = useState('');
  const [err, setErr] = useState('');
  const data = edit.data;
  const busy = recompRole.isPending || recompGen.isPending;

  useEffect(() => { if (data) { setOv(data.overrides || {}); setTex(data.tex || ''); } }, [data]);

  const setField = (k, v) => setOv((o) => ({ ...o, [k]: v }));

  const submit = (mode) => {
    setErr('');
    const payload = mode === 'tex' ? { mode: 'tex', tex } : { mode: 'chips', overrides: ov };
    const opts = {
      onSuccess: (d) => {
        // Say when a value was rejected or trimmed — reopening with a value the PDF never
        // used is the silent-drop bug this replaced.
        (d?.notes || []).forEach((n) => toast.push(n, { warn: true, icon: 'flag' }));
        toast.push('Résumé recompiled', { icon: 'check' }); onSaved && onSaved(); onClose();
      },
      onError: (e) => { setErr(String(e.message || e)); toast.push('Compile failed — see the error below', { warn: true }); },
    };
    if (isRole) recompRole.mutate({ id: roleId, ...payload }, opts);
    else recompGen.mutate({ token, ...payload }, opts);
  };

  return (
    <Modal onClose={onClose} max={780}>
      <div className="modal-head">
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Edit this résumé</h3>
          <div className="t3" style={{ fontSize: 12.5, marginTop: 3 }}>Your edits — deterministic, no LLM. Recompiles the same constant-named PDF.</div>
        </div>
        <button className="x" onClick={onClose}><Icon name="x" size={18} /></button>
      </div>

      <div className="modal-body">
        <div className="seg" style={{ marginBottom: 18 }}>
          <button className={tab === 'chips' ? 'on' : ''} onClick={() => setTab('chips')}>Quick edit</button>
          <button className={tab === 'tex' ? 'on' : ''} onClick={() => setTab('tex')}>Raw .tex</button>
        </div>

        {!data || !ov ? <p className="t3" style={{ padding: 20 }}>Loading…</p> : tab === 'chips' ? (
          <div>
            <Field label="Role descriptor (headline phrasing)" value={ov.descriptor} disabled={busy}
              onChange={(v) => setField('descriptor', v)} placeholder="enterprise and fintech" />
            <div className="field">
              <label>5th experience bullet</label>
              <select className="inp" value={ov.p5 || ''} disabled={busy} onChange={(e) => setField('p5', e.target.value)}>
                {(data.p5_options || []).map((o) => (
                  <option key={o.key} value={o.key}>{o.key} — {cleanBullet(o.text).slice(0, 64)}…</option>
                ))}
              </select>
              <div className="hint">Only your confirmed-true bullets are listed — nothing fabricated.</div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Field label="Domain tags" value={ov.domain_add} disabled={busy} onChange={(v) => setField('domain_add', v)} placeholder=", Fintech, B2B" />
              <Field label="Product-skill tags" value={ov.product_add} disabled={busy} onChange={(v) => setField('product_add', v)} placeholder=", System Integrations" />
              <Field label="AI-skill tags" value={ov.ai_add} disabled={busy} onChange={(v) => setField('ai_add', v)} placeholder=", Claude Code, Prompt Engineering" />
              <Field label="Tools tags" value={ov.tools_add} disabled={busy} onChange={(v) => setField('tools_add', v)} placeholder=", SQL, Jira" />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginTop: 6, flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 13.5, fontWeight: 600 }}>Show IIM A/B education bullet</span>
                <div className={`toggle ${ov.edu_ab ? 'on' : ''}`} onClick={() => !busy && setField('edu_ab', !ov.edu_ab)} />
              </div>
              <div className="field" style={{ margin: 0 }}>
                <label style={{ marginBottom: 4 }}>Third project</label>
                <select className="inp" value={ov.third_project || 'vault7a'} disabled={busy} onChange={(e) => setField('third_project', e.target.value)}>
                  <option value="vault7a">VAULT7A (self-hosted infra)</option>
                  <option value="portfolio">Portfolio site</option>
                </select>
              </div>
            </div>
          </div>
        ) : (
          <div className="field" style={{ margin: 0 }}>
            <label>LaTeX source</label>
            <textarea className="inp" value={tex} onChange={(e) => setTex(e.target.value)} disabled={busy}
              spellCheck={false} style={{ minHeight: 340, fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 12.5, lineHeight: 1.45 }} />
            <div className="hint">Edit and recompile. A LaTeX error shows below; your last working PDF stays until a compile succeeds.</div>
          </div>
        )}

        {err && (
          <pre style={{ marginTop: 14, padding: 12, background: 'var(--red-bg)', border: '1px solid #F3CFC9', borderRadius: 10, color: 'var(--red)', fontSize: 12, whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto' }}>{err}</pre>
        )}
      </div>

      <div className="modal-foot">
        <button className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
        <button className="btn btn-pri" disabled={busy || !data} onClick={() => submit(tab)}>
          <Icon name={busy ? 'refresh' : 'spark'} size={16} style={busy ? { animation: 'spin 1s linear infinite' } : {}} /> {busy ? 'Compiling…' : 'Recompile PDF'}
        </button>
      </div>
    </Modal>
  );
}
