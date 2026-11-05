# adr-011 — Downloaded résumés carry the company; the constant filename stays on disk

- **Status:** accepted
- **Date:** 2026-09-04
- **Amends:** the locked must_have "Per-JD tailored PDF via rules + texlive, constant filename"
- **Tags:** ui, curated, cat:product

## Context

The project locked a constant résumé filename —
`Sai_Vardhan_Palli_Product_Manager_IIMB_CV.pdf` — so every recruiter receives the same clean,
deliberate name, and the owner never has to think about naming a file mid-application.

In practice it produced the opposite. Every download endpoint served that one name, and no
browser will overwrite a file that already exists: the second résumé downloaded in a sitting
lands in `~/Downloads` as `Sai_Vardhan_Palli_Product_Manager_IIMB_CV (1).pdf`, the third as
`(2)`, and so on. The owner applies to several roles in one sitting, so this is the normal
case, not an edge case.

The harm is not folder clutter. **An ATS uploads whatever the file on disk is called**, so the
recruiter receives `Sai_Vardhan_Palli_Product_Manager_IIMB_CV (3).pdf` — precisely the sloppy,
duplicated-looking artefact the constant filename was chosen to prevent. Reported by the owner
2026-09-04.

## Decision

The **file on disk keeps `config.PDF_OUTPUT_NAME`**; only the name the browser saves under
changes. A per-role or manually generated résumé is served as
`Sai_Vardhan_Palli_Product_Manager_IIMB_CV_<Company>.pdf`, where `<Company>` is the role's
company reduced to alphanumerics and capped at 24 characters (`Airtel Digital` →
`AirtelDigital`).

Two deliberate exceptions keep the original intent intact:

- The **master one-pager** (`/api/resume/master`) has no company and keeps the plain constant
  name. That is the file handed out for socials and referrals, where a company suffix would be
  wrong.
- A generated PDF with no company supplied also falls back to the plain name — the suffix is
  never invented.

A **Settings toggle** (`nameWithCompany`, default on) reverts to the strictly-constant name.
A failure reading settings falls back to the suffixed name rather than breaking the download;
a download is the last step before applying and must not depend on a settings read.

This **amends** the locked must_have rather than discarding it: the filename is still
deterministic, still generated, still never hand-typed — it is now unique per employer.

## Consequences

- Downloading five résumés in one sitting yields five distinctly named files. No `(1)`, `(2)`
  can reach a recruiter.
- The company name appears in the file the recruiter receives. This reads as tailoring rather
  than as leakage, and is standard practice; the owner chose it over a timestamp suffix for
  exactly that reason.
- The suffix depends on the company recorded against the role. Apply-queue roles always carry
  one. Manually generated résumés carry one only when the owner fills the optional Company
  field added in iteration 170; without it the plain name is served and the collision returns
  for that file.
- Nothing about the résumé's content, the on-disk layout, or `applied_index.resume` changes —
  those all still use the constant name.

## Notes

Implementation: `cockpit/api/service.py` (`download_filename`, `company_slug`,
`generated_company`), `cockpit/api/main.py` (`_send_pdf`, `pdf_role`, `pdf_generated`),
`engine/settings_store.py` (`nameWithCompany`), `cockpit/web/src/screens/Settings.jsx`.
Verified live against four real picked roles (Visa, Microsoft, Phonepe, Razorpay) — each
served a distinct `Content-Disposition` filename while `/api/resume/master` kept the plain one.
Covered by six tests in `tests/test_iter170.py`.
