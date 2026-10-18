# Frontend redesign review

The dashboard now uses warm neutral surfaces, a restrained terracotta accent, self-hosted Inter, and a consistent set of buttons, fields, badges, tabs, and line icons. The work reorganizes page layouts and actions throughout the product.

## Route review

Each surface was inspected at 1440 × 1000, 1366 × 900, 768 × 1024, and 390 × 844. An additional check covers 320px layouts.

| Surface | Layout and interaction review |
| --- | --- |
| `/` | Existing redirect to the incident stream retained. |
| Sign-in | Separate introduction and sign-in areas; labeled secret field; inline errors; responsive layout. |
| `/incidents` | One metrics strip, searchable incident stream, grouped status filter and pagination, contextual service activity. Mobile records stack without page overflow. |
| `/incidents/[id]` | Context and primary actions first, verified resolution form with Cancel/Save, assessment beside the evidence ledger, trace exploration below. |
| `/traces/[id]` | Quiet waterfall colors, legible axis endpoints, grouped controls, keyboard cursor, touch-friendly mobile event rows and contextual instructions. |
| `/state` | Timestamp and reconstruction action grouped; consistent inspector categories and intentional empty state. |
| `/graph` | Light nodes with affected/root-candidate distinctions, working overview map, accessible zoom/pan controls. The overview moves away from the main dependency path. |
| `/counterfactual` | Intervention and recorded-window steps, contextual submit action, results comparison, clear simulation label and assumptions. Incident-linked windows retained. |
| `/settings` | Separate sections for credentials, operational configuration, and SDK setup; key creation beside its field; inline revoke confirmation; copy feedback. |
| Unknown routes | Branded 404 with a clear route back to incidents. |

The final pass corrected timeline label clipping, irrelevant desktop controls in the mobile trace list, excessive stacked panel spacing, weak secondary-text contrast, and a blank graph minimap.

## Verification

- Production build and TypeScript check passed.
- Existing Vitest suite: **12 / 12 passed**.
- Frontend Playwright suite: **20 / 20 passed**, including all route screenshots, root redirect, authentication errors and expiry, filters and pagination, resolution, keyboard replay, inspector tabs, three intervention request contracts, time-window validation, API-key lifecycle, sampling, mobile drawer focus, and graph controls.
- The 10,000-span waterfall stayed inside the existing 16ms p95 draw budget in the browser check.
- An axe audit using WCAG A/AA and WCAG 2.1 AA rules found **zero violations** across seven dashboard pages plus sign-in at desktop and mobile widths. This automated audit supplements the visual and keyboard review.
- Repository style check and `git diff --check` passed.

Browser checks use deterministic API and WebSocket fixtures in `e2e/ui-fixtures.ts`. No fixture or demo data is imported by the application. A live deployment, database, and full backend integration were not exercised.

Backend, SDKs, API client, generated contracts, schemas, WebSocket code, and query provider were left unchanged. Request payloads are covered by the browser regression checks.

## Run locally

From `dashboard/`:

```sh
npm ci
npx playwright install chromium
npm run lint
npm test
npm run test:ui
```

`test:ui` builds the dashboard and starts a local production server. It needs no backend or generated integration fixture. Screenshots are written to `test-results/`; the HTML report is under `playwright-report/ui/`. Existing real-stack tests remain available through `test:e2e` with their original generated fixture.

## Visual review artifacts

The browser suite generates screenshots for every route at four viewport sizes. It also captures resolution, simulation results, key creation, and empty/error states. These deterministic test artifacts stay out of the source repository; run `npm run test:ui` to produce and inspect them locally.
