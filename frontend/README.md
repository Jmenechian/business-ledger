# PC and mobile interface

Vue 3, strict TypeScript and Vite. Requires Node.js 22.12 or later. This is the writer interface; the offline laptop viewer and Drive integration are separate milestones.

From this directory:

```sh
npm ci
npm run build
npm test
npm run format:check
```

The backend serves `dist/index.html` and `dist/assets/` over its configured HTTPS origin. Build first, then start the Python server using the private password/certificate instructions in [backend setup](../backend/README.md). Static files and the login screen are public; ledger and work-session endpoints still require authentication. The CSP allows local compiled scripts/styles and same-origin API requests, with no inline scripts or external CDNs. There is no separate production API hostname, token storage or CORS exception.

## Synthetic preview

```sh
npm run dev
```

Open `http://127.0.0.1:5173/?demo=1`. The explicit demo switch uses an isolated in-memory adapter and synthetic fixtures; it never calls the ledger API or opens a database. Changes and demo work sessions reset when the page reloads. The Vite server binds only loopback. Its HTTP listener is for synthetic UI development, not operating a ledger.

## Workflows

- Search/select a client, or create an empty account.
- Read all eight accounting columns on desktop. Mobile offers a summary and a horizontally scrollable complete table.
- Register whole-number deliveries/payments. Payment amount and date are required; delivery dates and references are optional. Delivery price adjustment buttons round before calculating the total.
- Opening a customer account positions the history at its last movement. Refreshing the same account preserves the current position.
- While entering a delivery detail, select a price reference from that customer's own history. Matching tolerates accents, word order and typos. Selecting a reference fills only the price; other draft fields remain unchanged. Derived prices are marked and unknown historical creation dates remain unknown. Manual entry works even if lookup fails.
- Select a native movement to edit or delete. Imported history is protected; missing historical prices can be derived for presentation without writing them back.
- Start a work transfer, record activity across clients, then finish to see deliveries, payments, corrections, exact partial totals and client/activity details. History opens prior summaries. An open backend work transfer survives browser/server restarts.
- Select any row and choose **Descargar PDF desde aquí** for a direct statement download through the last row, named `Resumen <Cliente>.pdf`. No work transfer is required. Open the downloaded file to view/print it. The in-memory demo does not generate PDFs; the synthetic HTTPS browser test verifies the actual download.

All creation attempts retain one Idempotency-Key while the response is uncertain, including after closing/reopening the draft. The original customer, payload and work-session header are retained for that retry. A successful write stays confirmed if its later refresh fails. Corrections send If-Match revisions and refresh on conflict. Refreshing the entire page discards in-memory drafts; inspect history before manually recreating an operation whose result was uncertain. Logout is available independently of work-session closure; logging back in recovers the active backend group.

Work transfers are optional groups. Entries outside a manual group are recorded as individual local sessions by the backend. An active group is shared by PC/mobile, with one active group per ledger. Finishing never reapplies entries. The partial net is the group's debit changes minus credit changes, not the full account balance. No rollback or Drive action is exposed.

## Browser checks

From the repository root, first install Python runtime dependencies in `.venv`; from this directory:

```sh
npx playwright install chromium
npm run build
npm run test:e2e
```

Playwright checks desktop and emulated mobile against the isolated demo and an ephemeral HTTPS Python fixture. That fixture always generates a temporary database, password hash and certificate, cannot be pointed at an existing ledger, and has no business data. Self-signed certificate acceptance is limited to this fixture; operational clients must validate their configured certificate normally. Test output and screenshots stay local and outside Git.

The tests verify navigation, entries, corrections, protected history, HTML escaping, session summaries, login/logout, and recovery of an active group after reload. Actual phone/laptop hardware and browser compatibility still require device testing.
