# LeapLoop cockpit — multi-stage: build the React app, then a Python runtime that serves it
# alongside the FastAPI API and compiles tailored PDFs with a pre-warmed tectonic bundle.

# ---------- web build ----------
FROM node:20-slim AS web
WORKDIR /web
COPY cockpit/web/package.json cockpit/web/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY cockpit/web/ ./
RUN npm run build

# ---------- runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LEAPLOOP_DB=/data/leaploop.db \
    LEAPLOOP_DATA=/data \
    LEAPLOOP_SECRETS=/run/secrets/leaploop.env \
    LEAPLOOP_RESUME_DIR=/app/resume \
    LEAPLOOP_WEB_DIST=/app/cockpit/web/dist \
    TECTONIC_CACHE_DIR=/opt/tectonic-cache
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl fontconfig libfontconfig1 libgraphite2-3 libharfbuzz0b \
    && rm -rf /var/lib/apt/lists/*

# tectonic (self-contained LaTeX engine) via the official installer
RUN cd /usr/local/bin && curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh \
    && tectonic --version

COPY requirements.txt ./
COPY cockpit/requirements.txt ./cockpit-requirements.txt
RUN pip install -r requirements.txt -r cockpit-requirements.txt

# engine + resume first, then pre-warm the tectonic bundle by compiling the real resume once —
# bakes every LaTeX package the resume needs into the image (fast + offline at runtime). Placed
# before COPY cockpit so iterating on API/web code doesn't re-trigger the warm step.
COPY engine/ ./engine/
COPY resume/ ./resume/
RUN python -c "from engine import tailor; open('/tmp/warm.tex','w').write(tailor.render_tex('payments fintech platform b2b analytics')['tex'])" \
    && tectonic /tmp/warm.tex --outdir /tmp >/dev/null 2>&1 \
    && echo "tectonic bundle warmed ($(du -sh $TECTONIC_CACHE_DIR | cut -f1))"

COPY cockpit/ ./cockpit/
COPY scripts/ ./scripts/
COPY --from=web /web/dist ./cockpit/web/dist

EXPOSE 8509
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s \
    CMD curl -fsS http://127.0.0.1:8509/api/healthz || exit 1
CMD ["python", "-m", "uvicorn", "cockpit.api.main:app", "--host", "0.0.0.0", "--port", "8509"]
