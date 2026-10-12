#!/usr/bin/env bash
# Installs backend and frontend dependencies for the manual setup (SETUP.md, Path B).
# It does not install system tools (Python, Node, PostgreSQL) — see SETUP.md section 2.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1 — see SETUP.md section 2"; exit 1; }; }
need python3
need node
need npm

python3 - <<'EOF'
import sys
if sys.version_info < (3, 10):
    sys.exit(f"Python 3.10+ required, found {sys.version.split()[0]}")
EOF

echo "==> Backend"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements-dev.txt
if [ ! -f .env ]; then
  cp .env.example .env
  SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${SECRET}|" .env
  echo "Created backend/.env with a fresh JWT_SECRET (check DATABASE_URL)."
fi
deactivate

echo "==> Frontend"
cd "$ROOT/frontend"
[ -f .env.local ] || cp .env.example .env.local
npm install

cat <<'EOF'

Done. Next:
  1. Make sure PostgreSQL is running and DATABASE_URL in backend/.env is right (SETUP.md 2.5 / 6.1)
  2. Terminal 1:  cd backend && source .venv/bin/activate && alembic upgrade head && uvicorn app.main:app --reload
  3. Terminal 2:  cd frontend && npm run dev
  4. Open http://localhost:3000
EOF
