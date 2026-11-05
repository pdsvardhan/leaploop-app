# resume/

The real CV files are private and are not in this public copy. LeapLoop expects three LaTeX files here:

- `preamble.tex`: the layout and macros (included)
- `body.tex`: the master CV content, using those macros (not included)
- `GENERIC.tex`: a generic one-page variant (not included)

The live app mounts its own copies of these files at run time; `engine/tailor.py` rewrites the swappable lines
for each job description before compiling the PDF.
