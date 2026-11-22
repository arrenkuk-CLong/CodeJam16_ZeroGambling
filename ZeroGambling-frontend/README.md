# ZeroGambling frontend (Next.js)

The Lovable build's pages and components, running on Next.js and talking to the Django API in
`../ZeroGambling-backend`. Start Django first, then:

```powershell
npm install
npm run dev
```

Open http://localhost:3000. Requests to `/api/*` are forwarded to Django (`BACKEND_URL`, default
http://127.0.0.1:8000), so the browser only talks to this site.

## How the Lovable code maps onto Next.js

| Lovable (TanStack Start) | Here |
| --- | --- |
| `src/routes/*.tsx` | `components/pages/*.tsx` (unchanged apart from imports), rendered by `app/**/page.tsx` with the route's metadata |
| `src/routes/__root.tsx` | `app/layout.tsx` (fonts) + `components/Providers.tsx` (query client, account, preferences, header, toasts) |
| `createServerFn` in `lib/*.functions.ts` | Same names in `lib/zg.functions.ts`, `lib/world.functions.ts`, `lib/account.functions.ts`, each a POST to Django |
| TanStack `Link` / `useNavigate` | `lib/router.tsx` (same props, on the Next router) |
| Supabase auth | `lib/auth-client.ts` (the same `{ error }` calls, backed by Django accounts) |
| Server engine (`lib/engine/*.server.ts`), Postgres functions | Ported to Python in the Django backend; `lib/engine/*-types.ts` keep the shapes |
| `src/styles.css` | `app/globals.css` |

Shared, browser-safe rules stay in `lib/` exactly as Lovable wrote them (`catalog.ts`, `casino.ts`,
`collectibles.ts`, `economy-assets.ts`, `engine/slide-balance.ts`, ...). The server is authoritative for
every payout; these copies only drive what the UI shows.

- Type-check: `npx tsc --noEmit` · Lint: `npm run lint` · Production build: `npm run build`
- The slide game renderer is `components/slide/`, with sprites in `public/slide/`.
