/* API client + TanStack Query hooks. All server state flows through here. */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

async function req(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || j.error || detail; } catch {}
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}
const get = (p) => req('GET', p);
const post = (p, b) => req('POST', p, b);
const put = (p, b) => req('PUT', p, b);

/* ---------------- queries ---------------- */
export const useMe = () => useQuery({ queryKey: ['me'], queryFn: () => get('/api/me'), staleTime: 6e5 });
export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: () => get('/api/health'), refetchInterval: 60000 });
export const useRoles = (queue) =>
  useQuery({ queryKey: ['roles', queue], queryFn: () => get(`/api/roles?queue=${queue}`) });
export const useSettings = () => useQuery({ queryKey: ['settings'], queryFn: () => get('/api/settings') });
export const useIntegrations = () =>
  useQuery({ queryKey: ['integrations'], queryFn: () => get('/api/integrations'), refetchInterval: 60000 });
export const useJD = (id, enabled) =>
  useQuery({ queryKey: ['jd', id], queryFn: () => get(`/api/roles/${encodeURIComponent(id)}/jd`), enabled });

/* ---------------- mutations ---------------- */
function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['roles'] });
    qc.invalidateQueries({ queryKey: ['health'] });
  };
}

export function useDecide() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, decision }) => post(`/api/roles/${encodeURIComponent(id)}/decision`, { decision }),
    onSuccess: inv,
  });
}
export function useBulkDecide() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ ids, decision }) => post('/api/roles/bulk-decision', { ids, decision }),
    onSuccess: inv,
  });
}
export function useTailor() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, variant }) => post(`/api/roles/${encodeURIComponent(id)}/tailor`, { variant }),
    onSuccess: inv,
  });
}
export function useApplied() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, applied }) => post(`/api/roles/${encodeURIComponent(id)}/applied`, { applied }),
    onSuccess: inv,
  });
}
export function useGenerate() {
  return useMutation({ mutationFn: (body) => post('/api/generate', body) });
}
/* Log a manually generated CV as applied — writes the applied_index row the cleaner dedupes
   against, so a role you applied to outside the queue stops resurfacing in Triage. */
export function useLogGeneratedApplied() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ token, company, title, undo }) =>
      undo
        ? req('DELETE', `/api/generate/${encodeURIComponent(token)}/applied`)
        : post(`/api/generate/${encodeURIComponent(token)}/applied`, { company, title }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roles'] }),
  });
}

/* ---- per-JD résumé editor (item 307): chip edits + raw .tex ---- */
export const useRoleEdit = (id, enabled) =>
  useQuery({ queryKey: ['roleEdit', id], queryFn: () => get(`/api/roles/${encodeURIComponent(id)}/edit`), enabled, staleTime: 0 });
export function useRecompileRole() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, mode, overrides, tex }) => post(`/api/roles/${encodeURIComponent(id)}/recompile`, { mode, overrides, tex }),
    onSuccess: inv,
  });
}
export const useGenerateEdit = (token, enabled) =>
  useQuery({ queryKey: ['genEdit', token], queryFn: () => get(`/api/generate/${encodeURIComponent(token)}/edit`), enabled, staleTime: 0 });
export function useRecompileGenerated() {
  return useMutation({ mutationFn: ({ token, mode, overrides, tex }) => post(`/api/generate/${encodeURIComponent(token)}/recompile`, { mode, overrides, tex }) });
}
export function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch) => put('/api/settings', patch),
    onSuccess: (data) => qc.setQueryData(['settings'], data),
  });
}
export function useUnmute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (company) => post('/api/companies/unmute', { company }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] });
      qc.invalidateQueries({ queryKey: ['roles'] });
    },
  });
}

/* ---- résumé master freshness (item 888) ---- */
export const useResumeStatus = () =>
  useQuery({ queryKey: ['resumeStatus'], queryFn: () => get('/api/resume/status'), refetchInterval: 3e5 });
export function useMarkResumeReviewed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (note) => post('/api/resume/reviewed', { note: note || '' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['resumeStatus'] }),
  });
}

export const pdfRoleUrl = (id) => `/api/pdf/${encodeURIComponent(id)}`;
