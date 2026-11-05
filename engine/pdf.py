"""Compile a per-JD .tex to the constant-named PDF.

Strategy (first available wins):
  1. tectonic binary on PATH  (fast, self-contained)
  2. a persistent texlive container named $LEAPLOOP_TEX_CONTAINER (docker exec)
  3. ephemeral `docker run --rm` on $LEAPLOOP_TEX_IMAGE (default texlive/texlive:latest)

Runs the engine twice (refs/links). Output renamed to PDF_OUTPUT_NAME.
"""
from __future__ import annotations
import os, shutil, subprocess, sys
from pathlib import Path

try:
    from .config import PDF_OUTPUT_NAME
except ImportError:
    from config import PDF_OUTPUT_NAME

TEX_IMAGE = os.environ.get("LEAPLOOP_TEX_IMAGE", "texlive/texlive:latest")
TEX_CONTAINER = os.environ.get("LEAPLOOP_TEX_CONTAINER", "")


def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)[-1500:]


def _has(binary: str) -> bool:
    return shutil.which(binary) is not None


def compile_tex(tex_path: str | Path, out_name: str = PDF_OUTPUT_NAME) -> Path:
    tex_path = Path(tex_path).resolve()
    workdir = tex_path.parent
    stem = tex_path.stem
    log = ""
    rc = 1
    # Remove the stale intermediate PDF (cv.pdf) so a previous compile can't mask a failed one.
    # We deliberately KEEP the served out_name PDF: on a failed recompile the last working PDF
    # must survive (the editor promises this), and rc!=0 below still flags the failure.
    produced = workdir / f"{stem}.pdf"
    try:
        produced.unlink()
    except FileNotFoundError:
        pass

    if _has("tectonic"):
        rc, log = _run(["tectonic", str(tex_path), "--outdir", str(workdir)])
        engine = "tectonic"
    elif _has("docker") and TEX_CONTAINER:
        # persistent container: assumes workdir is bind-mounted at the same path inside
        for _ in range(2):
            rc, log = _run(["docker", "exec", "-w", str(workdir), TEX_CONTAINER,
                            "pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name])
        engine = f"docker exec {TEX_CONTAINER}"
    elif _has("docker"):
        for _ in range(2):
            rc, log = _run(["docker", "run", "--rm", "-v", f"{workdir}:/work", "-w", "/work",
                            TEX_IMAGE, "pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name])
        engine = f"docker run {TEX_IMAGE}"
    else:
        raise RuntimeError("No LaTeX engine: install tectonic or docker (texlive image).")

    if rc != 0 or not produced.exists():
        raise RuntimeError(f"LaTeX compile failed via {engine} (exit {rc}). Tail of log:\n{log}")
    out = workdir / out_name
    if produced != out:
        shutil.copyfile(produced, out)
    return out


def compile_tex_safe(tex_path: str | Path, out_name: str = PDF_OUTPUT_NAME) -> tuple[Path | None, str]:
    """Like compile_tex but never raises — returns (pdf_path_or_None, error_log).
    Used by the raw-.tex editor so a bad edit shows the LaTeX error inline instead of 500ing."""
    try:
        return compile_tex(tex_path, out_name), ""
    except Exception as e:
        return None, str(e)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python pdf.py <file.tex> [out_name]")
        sys.exit(2)
    out_name = sys.argv[2] if len(sys.argv) > 2 else PDF_OUTPUT_NAME
    pdf = compile_tex(sys.argv[1], out_name)
    print(f"PDF: {pdf} ({pdf.stat().st_size} bytes)")
