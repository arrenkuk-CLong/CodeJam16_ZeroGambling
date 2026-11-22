# ZeroGambling backend (Django)

Django owns every rule: challenge generation and grading, the gem wallet (exact cents) and ledger, casino
randomness and settlement, the shop, Trader Alex, the slide game and accounts. The Next.js frontend only
displays and animates what this API returns. This is a Python port of the Lovable build (TypeScript server
functions + Postgres functions); each Postgres function is now a Django transaction that locks the player row,
and every request carries a client request ID so retries can't pay or charge twice.

## Run it (Windows, PowerShell)

```powershell
cd ZeroGambling-backend
py -3 -m venv venv                 # first time only
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py runserver
```

Then, in a second terminal, start the frontend (`cd ZeroGambling-frontend`, `npm install`, `npm run dev`)
and open http://localhost:3000. Next.js forwards `/api/*` to Django on port 8000.

- Tests: `venv\Scripts\python manage.py test core` (Lovable's engine, casino, slide, collectible and account
  suites, plus API tests for settlement, idempotency, accounts and password reset)
- Database: SQLite by default; set `DATABASE_URL=postgres://...` for PostgreSQL.
- Password-reset emails print in the runserver terminal (console mailer); links only point at `FRONTEND_ORIGINS`.
- Slide balance table: `venv\Scripts\python manage.py slide_table`
- Admin: `venv\Scripts\python manage.py createsuperuser`, then http://127.0.0.1:8000/admin/

## Players and accounts

A guest is identified by a random token kept in the browser (only its SHA-256 is stored). Signing up or in
gives an account a bearer token (`Authorization: Bearer <key>`); the first time an account signs in on a
browser it adopts that browser's guest progress, once. The `Player` row stays the single source of truth for
gems and progress either way.

## Where things live (`core/`)

| File | What it does |
| --- | --- |
| `models.py` | Tables: players, account profiles, challenge runs/mastery/completions, wallet ledger, casino sessions/rounds, inventory, trophies, loss ledger, preferences, slide runs |
| `views.py`, `urls.py` | One POST endpoint per Lovable server function (same inputs and outputs) |
| `services.py` | Players, the wallet, challenge issue/actions/settlement, summary |
| `challenges.py`, `challenge_catalog.py`, `challenge_data.json` | The 19 challenge generators and graders, catalog and word lists |
| `casino_rules.py`, `casino_engine.py` | Versioned casino manifest (15 tables) and the seven game engines |
| `world.py` | World state, multi-asset stakes and settlement, shop, collectible batches, trades, preferences |
| `slide.py`, `slide_balance.py` | Slide game runs and glider upgrades; every slide balance number |
| `economy.py` | Challenge payout rules and asset valuation, V(p) = B(0.5p + 0.5p²) |
| `shop_catalog.py` | Glider, collectible tiers and odds, Trader Alex's offers |
| `accounts.py`, `authentication.py` | Sign-up/in, password reset, username/email/password changes, deletion |
| `jscompat.py` | JavaScript-compatible rounding, number formatting and the seeded PRNG used by the generators |
