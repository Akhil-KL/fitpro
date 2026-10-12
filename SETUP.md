# fitpro — Setup Guide

Everything you need to download, install, configure and run fitpro on your machine (Linux / Ubuntu),
from a code editor such as VS Code. Pick **one** of the two paths:

- **Path A — Docker** (fewest installs, runs database + backend + frontend together)
- **Path B — Manual** (Python + Node + PostgreSQL installed directly; best for editing code in VS Code)

Project location used below: `/home/svce/fitpro`

---

## 1. What you need to download

| Tool | Version | Needed for | Path A | Path B |
|---|---|---|---|---|
| Git | any | cloning / version control | optional | optional |
| unzip | any | extracting `fitpro.zip` | yes | yes |
| Docker Engine + Compose plugin | 24+ / v2.24+ | running everything in containers | **yes** | no |
| Python | 3.10 – 3.12 (3.12 recommended) | backend | no | **yes** |
| Node.js (includes npm) | 20 LTS or newer | frontend | no | **yes** |
| PostgreSQL | 14 – 16 | database | no | **yes** (or use SQLite, see 5.3) |
| VS Code | latest | editing | optional | optional |
| OpenAI API key | — | smarter chat parsing (optional) | optional | optional |

Check what you already have:

```bash
git --version; unzip -v | head -1; docker --version; docker compose version
python3 --version; node --version; npm --version; psql --version
```

---

## 2. Install the tools (Ubuntu / Debian)

### 2.1 Basics

```bash
sudo apt update
sudo apt install -y git curl unzip build-essential
```

### 2.2 Docker (Path A)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER        # lets you run docker without sudo
newgrp docker                        # or log out and back in
docker run --rm hello-world          # should print "Hello from Docker!"
```

### 2.3 Python (Path B)

```bash
sudo apt install -y python3 python3-venv python3-pip python3-dev libpq-dev
python3 --version                    # must be 3.10 or newer
```

### 2.4 Node.js 20 (Path B)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version                       # v20.x or newer
```

### 2.5 PostgreSQL (Path B)

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

# Create the database user and database used by fitpro
sudo -u postgres psql -c "CREATE USER fitpro WITH PASSWORD 'fitpro';"
sudo -u postgres psql -c "CREATE DATABASE fitpro OWNER fitpro;"

# Test the connection
psql "postgresql://fitpro:fitpro@localhost:5432/fitpro" -c "select 1;"
```

> Change the password `fitpro` for anything other than local development, and use the same value in `DATABASE_URL`.

### 2.6 VS Code and extensions (optional)

Download VS Code from https://code.visualstudio.com, or `sudo snap install code --classic`. Then:

```bash
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension dbaeumer.vscode-eslint
code --install-extension bradlc.vscode-tailwindcss
code --install-extension ms-azuretools.vscode-docker
code --install-extension charliermarsh.ruff
```

In VS Code, after creating the backend virtual environment (step 5.1), choose
**Python: Select Interpreter → `backend/.venv/bin/python`**.

---

## 3. Get the project

```bash
cd /home/svce
unzip fitpro.zip            # creates /home/svce/fitpro
cd fitpro
code .                      # open in VS Code (optional)
```

Folder overview:

```
fitpro/
├── SETUP.md               ← this file
├── README.md              architecture and feature overview
├── setup.sh               installs backend + frontend dependencies for Path B
├── docker-compose.yml     Path A
├── docs/                  original product specs
├── backend/               FastAPI app (Python)
└── frontend/              Next.js app (TypeScript)
```

---

## 4. Path A — run with Docker

```bash
cd /home/svce/fitpro
cp backend/.env.example backend/.env       # then edit it (see section 6)
docker compose up --build
```

First build takes a few minutes. When the logs settle:

| What | URL |
|---|---|
| App | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

Stop with `Ctrl+C`; `docker compose down` removes the containers (data stays in Docker volumes);
`docker compose down -v` also deletes the database and uploads.

Useful commands:

```bash
docker compose logs -f backend                       # backend logs
docker compose exec backend pytest                   # run backend tests in the container
docker compose exec db psql -U fitpro fitpro         # open a database shell
docker compose up --build backend                    # rebuild after code changes
```

---

## 5. Path B — run manually (two terminals)

Quick way: `bash setup.sh` does steps 5.1 and 5.2 for you. The manual steps are below.

### 5.1 Backend (terminal 1)

```bash
cd /home/svce/fitpro/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt

cp .env.example .env          # then edit it (see section 6)
alembic upgrade head          # creates all 18 tables in PostgreSQL
uvicorn app.main:app --reload --port 8000
```

On first start the backend seeds about 45 foods. Check: http://localhost:8000/health

### 5.2 Frontend (terminal 2)

```bash
cd /home/svce/fitpro/frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

### 5.3 No PostgreSQL? Use SQLite for a quick try

In `backend/.env` set:

```
DATABASE_URL=sqlite:///./fitpro.db
AUTO_CREATE_TABLES=true
```

Skip `alembic upgrade head`; tables are created on start. Use PostgreSQL for anything real.

### 5.4 Run the tests

```bash
cd /home/svce/fitpro/backend && source .venv/bin/activate
pytest                         # 44 tests, uses an in-memory database
cd ../frontend && npm run typecheck
```

---

## 6. Configuration values

### 6.1 `backend/.env`

Generate a secret first:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Minimal working file (Path B with local PostgreSQL):

```env
ENVIRONMENT=development
DATABASE_URL=postgresql+psycopg://fitpro:fitpro@localhost:5432/fitpro
AUTH_MODE=local
JWT_SECRET=<paste the generated secret>
OPENAI_API_KEY=
STORAGE_BACKEND=local
LOCAL_STORAGE_DIR=./storage
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
```

With Docker (Path A) you don't need `DATABASE_URL`; `docker-compose.yml` sets it to the `db` container.

All backend settings:

| Variable | Default | Meaning |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` hides `/docs` and the dev password-reset link |
| `DATABASE_URL` | postgres on localhost | SQLAlchemy URL. PostgreSQL: `postgresql+psycopg://USER:PASS@HOST:5432/DB` |
| `AUTO_CREATE_TABLES` | `false` | `true` creates tables without Alembic (SQLite/dev only) |
| `AUTH_MODE` | `local` | `local` = email + password handled by the backend; `supabase` = Supabase Auth |
| `JWT_SECRET` | placeholder | **Change it.** Signs login tokens in `local` mode |
| `ACCESS_TOKEN_MINUTES` | `1440` | Login lifetime (24 h) |
| `PASSWORD_RESET_MINUTES` | `30` | Reset-link lifetime |
| `OPENAI_API_KEY` | empty | Optional. Empty = built-in rule parser |
| `OPENAI_MODEL` | `gpt-4o-mini` | Any model that supports Structured Outputs |
| `CHAT_CONTEXT_MESSAGES` | `8` | Recent messages sent to the model |
| `STORAGE_BACKEND` | `local` | `local` disk or `supabase` Storage for uploaded plans |
| `LOCAL_STORAGE_DIR` | `./storage` | Where uploads go in `local` mode |
| `MAX_UPLOAD_MB` | `5` | Workout-plan upload limit |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed frontend URLs |
| `FRONTEND_URL` | `http://localhost:3000` | Used to build password-reset links |
| `CHAT_RATE_LIMIT_PER_MINUTE` | `30` | Chat messages per user per minute |
| `SUPABASE_URL` | — | `https://<project>.supabase.co` (Supabase mode / storage) |
| `SUPABASE_JWT_SECRET` | — | Project JWT secret (Supabase → Project Settings → API) |
| `SUPABASE_SERVICE_KEY` | — | Service-role key, **server only**, for Storage uploads |
| `SUPABASE_STORAGE_BUCKET` | `workout-plans` | Private bucket name |

### 6.2 `frontend/.env.local`

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_AUTH_MODE=local
# Only for NEXT_PUBLIC_AUTH_MODE=supabase:
# NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
# NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon public key>
```

`NEXT_PUBLIC_AUTH_MODE` must match the backend's `AUTH_MODE`. For Docker, these are build args in
`docker-compose.yml` — change them there and rebuild.

### 6.3 Optional: OpenAI key

1. Create a key at https://platform.openai.com/api-keys (needs billing enabled).
2. Put it in `backend/.env` as `OPENAI_API_KEY=sk-...` and restart the backend.
3. http://localhost:8000/health shows `"ai": "openai"` when it's active (`"rules"` otherwise).

Without a key, logging, corrections, queries and plan import all still work.

### 6.4 Optional: Supabase (auth, database, storage)

1. Create a project at https://supabase.com.
2. Database: copy the connection string (Project Settings → Database), change the prefix to
   `postgresql+psycopg://`, put it in `DATABASE_URL`, run `alembic upgrade head`.
3. Auth: set `AUTH_MODE=supabase`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET` in the backend; set
   `NEXT_PUBLIC_AUTH_MODE=supabase`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` in the frontend.
4. Storage: create a **private** bucket `workout-plans`, set `STORAGE_BACKEND=supabase` and `SUPABASE_SERVICE_KEY`.

---

## 7. Dependencies that get downloaded

You don't install these by hand — `pip install` and `npm install` fetch them — but here is the full list.

**Backend (`backend/requirements.txt`)**

```
fastapi  uvicorn[standard]  pydantic  pydantic-settings  SQLAlchemy  alembic
psycopg[binary]  PyJWT[crypto]  pwdlib[argon2]  python-multipart  httpx
openai  PyMuPDF  tzdata  email-validator
dev: pytest  ruff
```

**Frontend (`frontend/package.json`)**

```
next  react  react-dom  recharts  @supabase/supabase-js
dev: typescript  tailwindcss  postcss  autoprefixer  eslint  eslint-config-next
     @types/node  @types/react  @types/react-dom
```

Docker images (Path A): `postgres:16-alpine`, `python:3.12-slim`, `node:20-alpine`.

---

## 8. First use

1. Open http://localhost:3000 → **Create an account**.
2. Fill in the profile (age, sex, height, weight, activity, goal) → you get calorie, protein and water targets.
3. In **Chat**, try:
   - `I ate 3 eggs, 200g rice and 150g chicken for lunch`
   - `Actually, the rice was 250g`
   - `I ate some chicken` → answer `150`
   - `I ate 100g homemade protein atta` → answer `100g contains 350 kcal, 25g protein, 50g carbs, 8g fat`
   - `Bench press 60kg 4x8` · `My weight today is 66.8kg` · `I drank 750ml water`
   - `How much protein have I eaten today?`
4. **Workouts** → import a `.txt` plan like the one below, then ask the chat `What is today's workout?`

```
My PPL
Day 1 - Push
Bench Press 4x8
Incline DB Press 3x10
Lateral Raise 3x15
Day 2 - Pull
Deadlift 3x5
Pull ups 4x8
Day 3 - Legs
Squat 5x5
Plank 3x60s
```

5. **Today** and **Progress** show the charts built from what you logged.

---

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `Can't reach the server` in the app | Backend isn't running or `NEXT_PUBLIC_API_URL` is wrong. Check http://localhost:8000/health |
| Browser console shows a CORS error | Add the exact frontend URL to `CORS_ORIGINS` and restart the backend |
| `connection refused` / `password authentication failed` for Postgres | Postgres not running (`sudo systemctl start postgresql`) or `DATABASE_URL` user/password don't match section 2.5 |
| `relation "users" does not exist` | Run `alembic upgrade head` (or set `AUTO_CREATE_TABLES=true` for SQLite) |
| `ModuleNotFoundError` in the backend | Activate the venv: `source backend/.venv/bin/activate`, then `pip install -r requirements-dev.txt` |
| `Address already in use` on 8000/3000/5432 | Stop the other process (`sudo lsof -i :8000`) or change the port |
| `permission denied ... docker.sock` | `sudo usermod -aG docker $USER`, then log out and back in |
| `npm install` fails | Check `node --version` is 20+; delete `node_modules` and `package-lock.json`, retry |
| Frontend build fails fetching Google Fonts | The build needs internet once; run it on a connected network |
| Uploaded PDF shows "No readable text found" | It's a scanned image PDF; export a text PDF or save the plan as `.txt` |
| Logged out after a day | Normal: tokens last `ACCESS_TOKEN_MINUTES` (24 h) |
| Forgot password in development | The reset page shows a direct link because no email service is set up |

---

## 10. Command cheat sheet

```bash
# Path A
docker compose up --build          # start everything
docker compose down                # stop
docker compose exec backend pytest # tests

# Path B — backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload      # run
alembic upgrade head               # apply migrations
alembic revision --autogenerate -m "describe change"   # after editing models
pytest                             # tests
ruff check app tests               # lint

# Path B — frontend
cd frontend
npm run dev                        # run
npm run typecheck                  # type errors
npm run build && npm start         # production build
```
