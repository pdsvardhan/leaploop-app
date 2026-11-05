/* Tracker — searchable record of applications (company/role/resume/date/source/status), CSV export. */
import { useMemo } from 'react';
import { Icon } from '../icons.jsx';
import { CompanyLogo, EmptyState, useToast } from '../components.jsx';
import { useRoles } from '../api.js';

function toCSV(rows) {
  const head = ['Company', 'Role', 'Resume', 'Date', 'Source', 'Status'];
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const lines = [head.join(',')].concat(
    rows.map((r) => [r.co, r.role, r.resume, r.date, r.source, r.status].map(esc).join(',')));
  return lines.join('\n');
}

export function TrackerScreen({ query }) {
  const toast = useToast();
  const { data, isLoading } = useRoles('tracker');
  const rows = data?.rows || [];

  const shown = useMemo(() => {
    if (!query.trim()) return rows;
    const k = query.toLowerCase();
    return rows.filter((r) => r.co.toLowerCase().includes(k) || r.role.toLowerCase().includes(k));
  }, [rows, query]);

  const exportCsv = () => {
    const blob = new Blob([toCSV(shown)], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `leaploop-tracker-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast.push(`Exported ${shown.length} rows to CSV`, { icon: 'download' });
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Tracker</h1>
          <p className="page-sub">{rows.length} applications recorded · auto-marked from Gmail confirmations.</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={exportCsv}><Icon name="download" size={17} /> Export CSV</button>
        </div>
      </div>

      <div className="card" style={{ padding: '16px 8px 6px' }}>
        {isLoading ? <div className="t3" style={{ padding: 30, textAlign: 'center' }}>Loading…</div> :
          shown.length === 0 ? (
            <EmptyState icon="tracker" title={rows.length === 0 ? 'No applications yet' : 'No matches'}
              text={rows.length === 0 ? 'Applications you mark applied — and ones Gmail confirms — land here.' : 'Try a different search term.'} />
          ) : (
            <table className="tbl">
              <thead>
                <tr><th>Company</th><th>Role</th><th>Resume submitted</th><th>Date</th><th>Source</th><th>Status</th></tr>
              </thead>
              <tbody>
                {shown.map((r, i) => (
                  <tr key={i}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                        <CompanyLogo co={r.co} size={34} r={10} />
                        <span style={{ fontWeight: 700 }} data-mob-label="Company">{r.co}</span>
                      </div>
                    </td>
                    <td className="muted" data-mob-label="Role">{r.role}</td>
                    <td><span className="pdf-chip"><Icon name="doc" size={14} />{r.resume}</span></td>
                    <td className="t3" data-mob-label="Date">{r.date}</td>
                    <td><span className="chip"><Icon name={r.source === 'ATS' ? 'shield' : 'link'} size={13} />{r.source}</span></td>
                    <td><span className="st applied">Applied</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  );
}
