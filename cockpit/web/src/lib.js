/* Small pure helpers: brand colors, the locked referral template, the honest fit band. */

// Known brand hues (from the reference); everything else gets a stable hash-derived hue.
const BRAND = {
  razorpay: '#1A56DB', cred: '#1A1A1A', zerodha: '#387ED1', postman: '#EF5B25',
  atlassian: '#2563EB', sprinto: '#6D28D9', swiggy: '#FC8019', phonepe: '#5F259F',
  meesho: '#E60073', groww: '#00B386', freshworks: '#0B5CD5', zepto: '#7B1FA2',
  paytm: '#012B72', amazon: '#FF9900', google: '#4285F4', microsoft: '#0078D4',
  flipkart: '#2874F0', stripe: '#635BFF', uber: '#000000', visa: '#1A1F71',
  mastercard: '#EB001B', hdfc: '#004C8F', 'yes bank': '#00518F',
};

export function companyHue(co) {
  const key = (co || '').toLowerCase().trim();
  if (BRAND[key]) return BRAND[key];
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) % 360;
  return `hsl(${h}, 52%, 42%)`;
}

export function shade(hex, pct) {
  if (!hex.startsWith('#')) return hex; // hsl() brand fallback — leave as-is
  const n = parseInt(hex.slice(1), 16);
  let r = (n >> 16) + Math.round(2.55 * pct);
  let g = ((n >> 8) & 255) + Math.round(2.55 * pct);
  let b = (n & 255) + Math.round(2.55 * pct);
  r = Math.max(0, Math.min(255, r)); g = Math.max(0, Math.min(255, g)); b = Math.max(0, Math.min(255, b));
  return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}

export function logoText(name) {
  return (name || '?').length <= 4 ? (name || '?').slice(0, 2).toUpperCase() : (name || '?').slice(0, 2);
}

// Honest fit: a transparent count of resume themes the JD overlaps — NOT a weighted rank.
// null/undefined means the role was never scored because it has no JD. That is NOT the same as
// 0 ("scored, nothing overlapped"), and it must not render as a fit band at all (item 886).
export function fitBand(hits) {
  if (hits === null || hits === undefined) {
    return { label: 'No JD', tone: 'u', word: 'Not scored', unscored: true };
  }
  if (hits >= 6) return { label: 'Strong fit', tone: 'a', word: 'Strong' };
  if (hits >= 3) return { label: 'Partial fit', tone: 'b', word: 'Partial' };
  if (hits >= 1) return { label: 'Light fit', tone: 'c', word: 'Light' };
  return { label: 'Safe master', tone: 'u', word: 'Default' };
}

const GAP_LABEL = {
  growth: 'growth metrics', fintech_specialist: 'fintech-specialist', ml_modeling: 'ML modeling',
  gtm: 'GTM / launch', analytics_tools: 'named analytics tools', seniority: '5+ yr seniority',
};
export const gapLabel = (g) => GAP_LABEL[g] || g;

// LOCKED verbatim referral template — only <name>/<role>/<company> are filled (brief §3).
export function referralDraft(name, role, company) {
  return (
    `Hi ${name || '<name>'}, thanks for connecting!\n` +
    `I came across a ${role} role at ${company}, and felt it aligns well with my background. ` +
    `Wanted to check if you'd be open to referring me for the role. ` +
    `Happy to share my resume and any additional details if helpful.\n` +
    `Thanks!`
  );
}
