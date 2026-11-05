/* Generate PDF — paste JD text OR a role URL, get a tailored PDF (bypasses sourcing/filtering). */
import { useState, useEffect } from 'react';
import { Icon } from '../icons.jsx';
import { useToast } from '../components.jsx';
import { useGenerate, useResumeStatus, useMarkResumeReviewed, useLogGeneratedApplied } from '../api.js';
import { fitBand, gapLabel } from '../lib.js';
import { ResumeEditor } from '../ResumeEditor.jsx';
import { PREFILL_KEY } from './Triage.jsx';

/* Freshness guard (item 888): a résumé that still says "Present" for a role you have left will
   generate a confidently wrong PDF. Warn — never block; sending is the owner's call. */
function ResumeFreshness() {
  const { data } = useResumeStatus();
  const mark = useMarkResumeReviewed();
  const warnings = data?.warnings || [];
  if (!warnings.length) return null;
  return (
    <div className="card card-pad enter" style={{ marginBottom: 18, borderColor: '#F0DDB0', background: 'var(--amber-bg)' }}>
      {warnings.map((w) => (
        <div key={w.code} style={{ display: 'flex', gap: 11, alignItems: 'flex-start', marginBottom: 8 }}>
          <Icon name="flag" size={17} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: 2 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--amber)' }}>
              {w.level === 'warn' ? 'Check your résumé before sending' : 'Résumé changed'}
            </div>
            <div style={{ fontSize: 13.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>{w.message}</div>
          </div>
        </div>
      ))}
      <button className="btn btn-soft btn-sm" disabled={mark.isPending}
        onClick={() => mark.mutate('confirmed from Generate')}>
        <Icon name="check" size={15} /> It's current — stop warning me
      </button>
    </div>
  );
}

export function GenerateScreen() {
  const toast = useToast();
  const gen = useGenerate();
  const [mode, setMode] = useState('text');
  const [val, setVal] = useState('');
  const [co, setCo] = useState('');
  const [ti, setTi] = useState('');
  const [result, setResult] = useState(null);
  const [editOpen, setEditOpen] = useState(false);
  const [rev, setRev] = useState(0);   // cache-buster so the iframe reloads after an edit
  const logApplied = useLogGeneratedApplied();
  const [logged, setLogged] = useState(false);

  // Handed over from a Triage role that had no JD attached. Deliberately lands in TEXT mode:
  // these are LinkedIn postings, and LeapLoop never fetches LinkedIn pages (locked non_goal).
  // The URL is shown to open manually, never submitted for fetching.
  const [postingUrl, setPostingUrl] = useState(null);
  useEffect(() => {
    let pre = null;
    try {
      pre = sessionStorage.getItem(PREFILL_KEY);
      if (pre !== null) sessionStorage.removeItem(PREFILL_KEY);
    } catch { /* private mode */ }
    if (pre) { setMode('text'); setVal(''); setPostingUrl(pre); }
  }, []);

  const generate = () => {
    if (!val.trim()) { toast.push('Paste a JD or a role URL first', { warn: true, icon: 'snooze' }); return; }
    setResult(null);
    setLogged(false);
    const body = mode === 'text' ? { text: val } : { url: val };
    gen.mutate({ ...body, company: co, title: ti }, {
      onSuccess: (d) => { setResult(d); toast.push('Tailored PDF ready', { icon: 'check' }); },
      onError: (e) => toast.push(e.message || 'Could not generate', { warn: true }),
    });
  };
  const markApplied = () => {
    const undo = logged;
    logApplied.mutate({ token: result.token, company: co, title: ti, undo }, {
      onSuccess: (d) => {
        setLogged(!undo);
        const msg = undo
          ? (d.kept_existing ? `${d.company} was already in your tracker — nothing removed`
                             : `Applied log removed · ${d.company}`)
          : (d.already_tracked ? `${d.company} was already in your tracker`
                               : `Logged as applied · ${d.company}`);
        toast.push(msg, { icon: undo ? 'refresh' : 'check' });
      },
      onError: (e) => toast.push(e.message || 'Could not log it', { warn: true }),
    });
  };
  const reset = () => { setVal(''); setResult(null); setLogged(false); };
  const working = gen.isPending;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Generate PDF</h1>
          <p className="page-sub">Found a role yourself? Paste it here and skip the queue.</p>
        </div>
      </div>

      <ResumeFreshness />

      {postingUrl && (
        <div className="card card-pad enter" style={{ marginBottom: 18, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <Icon name="link" size={19} style={{ color: 'var(--g-700)', flexShrink: 0 }} />
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>This role came with no job description</div>
            <div className="muted" style={{ fontSize: 13, lineHeight: 1.45 }}>
              Open the posting, copy the description, and paste it below. LeapLoop never fetches
              LinkedIn pages itself.
            </div>
          </div>
          <a className="btn btn-soft btn-sm" href={postingUrl} target="_blank" rel="noreferrer">
            <Icon name="external" size={15} /> Open posting
          </a>
          <button className="btn btn-ghost btn-sm" onClick={() => setPostingUrl(null)} title="Dismiss">
            <Icon name="x" size={15} />
          </button>
        </div>
      )}

      <div className="card card-pad enter" style={{ marginBottom: 18, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ width: 46, height: 46, borderRadius: 13, background: 'var(--g-700)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', flexShrink: 0 }}>
          <Icon name="doc" size={22} />
        </div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Your master résumé</h3>
          <p className="muted" style={{ margin: '3px 0 0', fontSize: 13, lineHeight: 1.45 }}>The clean default one-pager — handy for socials, referrals, or a quick send. The generator below tailors a per-JD variant from this same base.</p>
        </div>
        <div style={{ display: 'flex', gap: 9 }}>
          <a className="btn btn-soft" href="/api/resume/master" target="_blank" rel="noreferrer"><Icon name="eye" size={16} /> Preview</a>
          <a className="btn btn-pri" href="/api/resume/master" download><Icon name="download" size={16} /> Download</a>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }} className="gen-split">
        <div className="card card-pad">
          <div className="seg" style={{ marginBottom: 18 }}>
            <button className={mode === 'text' ? 'on' : ''} onClick={() => setMode('text')}>Paste JD text</button>
            <button className={mode === 'url' ? 'on' : ''} onClick={() => setMode('url')}>Paste role URL</button>
          </div>
          {mode === 'text' ? (
            <div className="field">
              <label>Job description</label>
              <textarea className="inp" placeholder="Paste the full JD here…" value={val} onChange={(e) => setVal(e.target.value)} style={{ minHeight: 220 }} disabled={working} />
              <div className="hint">The rules engine matches JD keywords to your resume themes — deterministic, no LLM.</div>
            </div>
          ) : (
            <div className="field">
              <label>Role URL</label>
              <input className="inp" placeholder="https://boards.greenhouse.io/acme/jobs/123" value={val} onChange={(e) => setVal(e.target.value)} disabled={working} />
              <div className="hint">Best effort — Greenhouse / Lever JDs fetch cleanly; for others, paste the text.</div>
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="field">
              <label>Company (optional)</label>
              <input className="inp" placeholder="Razorpay" value={co} disabled={working}
                onChange={(e) => setCo(e.target.value)} />
            </div>
            <div className="field">
              <label>Role title (optional)</label>
              <input className="inp" placeholder="Senior Product Manager" value={ti} disabled={working}
                onChange={(e) => setTi(e.target.value)} />
            </div>
          </div>
          <div className="hint" style={{ marginTop: -8, marginBottom: 12 }}>
            The title is scored 3× a mention in the JD body, and both are needed to log this as
            applied so the role stops resurfacing in Triage.
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button className="btn btn-pri btn-lg" onClick={generate} disabled={working}>
              {working ? <><Icon name="refresh" size={18} style={{ animation: 'spin 1s linear infinite' }} /> Generating…</> : <><Icon name="spark" size={18} /> Tailor my resume</>}
            </button>
            {(result || val) && !working && <button className="btn btn-ghost btn-lg" onClick={reset}>Clear</button>}
          </div>
        </div>

        <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column' }}>
          {!result && !working && (
            <div className="empty" style={{ padding: '40px 20px', margin: 'auto' }}>
              <div className="empty-ic"><Icon name="pdf" size={34} /></div>
              <h3>Your tailored PDF lands here</h3>
              <p>Paste a JD on the left and hit tailor.</p>
            </div>
          )}
          {working && (
            <div className="empty" style={{ padding: '40px 20px', margin: 'auto' }}>
              <div className="empty-ic"><Icon name="refresh" size={30} style={{ animation: 'spin 1s linear infinite' }} /></div>
              <h3>Tailoring…</h3>
              <p>Matching JD themes, assembling LaTeX, compiling the PDF.</p>
            </div>
          )}
          {result && (
            <div className="enter" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
                <span className="st applied">Ready</span>
                <span style={{ fontWeight: 700, fontSize: 14 }}>{result.variant}</span>
                <span className="chip"><Icon name="spark" size={13} />{fitBand(result.fit).word} · {result.fit} theme matches</span>
              </div>
              {result.gaps?.length > 0 && (
                <div className="t3" style={{ fontSize: 12.5, marginBottom: 10 }}>Honest gaps: {result.gaps.map(gapLabel).join(' · ')}</div>
              )}
              <iframe title="Generated resume" src={`${result.pdf_url}?rev=${rev}#toolbar=0&view=FitH`} style={{ width: '100%', flex: 1, minHeight: 280, border: '1px solid var(--line)', borderRadius: 8, background: '#fff' }} />
              <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
                <a className="btn btn-pri" href={`${result.pdf_url}?rev=${rev}`} download><Icon name="download" size={17} /> Download PDF</a>
                <button className="btn btn-ghost" onClick={() => setEditOpen(true)}><Icon name="edit" size={17} /> Edit</button>
                {result.apply_url && <a className="btn btn-ghost" href={result.apply_url} target="_blank" rel="noreferrer"><Icon name="external" size={17} /> Apply</a>}
                <button className="btn btn-ghost" onClick={markApplied} disabled={logApplied.isPending}
                  title={logged ? 'Remove the tracker row this added'
                    : (co ? 'Record this in the tracker so the role stops resurfacing in Triage'
                      : 'Add the company name first')}>
                  <Icon name={logged ? 'refresh' : 'doc'} size={17} /> {logged ? 'Undo applied log' : 'Log as applied'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {editOpen && result?.token && (
        <ResumeEditor token={result.token} onClose={() => setEditOpen(false)} onSaved={() => setRev((n) => n + 1)} />
      )}
    </div>
  );
}
