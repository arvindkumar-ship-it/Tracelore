import type { Page } from "@playwright/test";

export const incidentId = "11111111-1111-4111-8111-111111111111";
export const traceId = "22222222-2222-4222-8222-222222222222";
export const secret = "test-dashboard-secret";
const now = Date.now();
const ago = (minutes: number) => new Date(now - minutes * 60_000).toISOString();
const eventId = (n: number) =>
  `60000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

export const incidents = [
  ["checkout", "inventory"],
  ["payments"],
  ["gateway", "checkout"],
  ["catalog"],
  ["inventory"],
  ["gateway", "payments"],
].map((services, i) => ({
  id:
    i === 0
      ? incidentId
      : `11111111-1111-4111-8111-${String(i + 1).padStart(12, "0")}`,
  status: i < 2 ? "open" : "resolved",
  opened_at: ago((i + 1) * 13),
  closed_at: i < 2 ? null : ago(i * 10),
  start_event_id: eventId(1),
  start_time: ago((i + 1) * 13 + 1),
  services,
  confidence: [0.96, 0.88, 0.93, 0.82, 0.91, 0.79][i],
  signals: [
    {
      id: `signal-${i}`,
      kind: "metric",
      service: services[0],
      route: "/checkout",
      detected_at: ago(12),
      estimated_start: ago(14),
      confidence: 0.96,
      event_id: eventId(1),
      trace_id: traceId,
    },
  ],
  updated_at: ago(1),
  version: 1,
  signal_count: [8, 4, 12, 3, 6, 5][i],
}));
export const live = {
  events_per_sec: 1248,
  error_rate: 0.023,
  per_service: {
    checkout: { count: 4290, errors: 12, p95_ms: 248.4 },
    payments: { count: 3120, errors: 4, p95_ms: 187.2 },
    gateway: { count: 2840, errors: 0, p95_ms: 42.8 },
    inventory: { count: 2230, errors: 0, p95_ms: 312.6 },
  },
  incidents: [],
  incident_version: 1,
  heartbeat: new Date().toISOString(),
};
export const rca = {
  incident_id: incidentId,
  source: "rules",
  report: {
    root_cause_node: "db:inventory",
    mechanism:
      "Inventory database latency increased before checkout errors appeared. Slow queries exhausted the inventory connection pool, delaying downstream requests.",
    confidence: 0.94,
    evidence_ids: ["evidence-1", "evidence-2", "evidence-3"],
    suggested_fix:
      "Inspect the slow inventory query and connection pool limits. Test a lower database latency before rolling out the change.",
    insufficient_evidence: false,
  },
  bundle: {
    candidates: [
      { node: "db:inventory", score: 0.94, parts: { temporal: 0.96 } },
    ],
    similar_incidents: [],
    evidence: [
      {
        id: "evidence-1",
        kind: "metric",
        node: "db:inventory",
        text: "Database p95 latency rose from 42 ms to 312 ms before the incident began.",
        data: { baseline_ms: 42, observed_ms: 312, magnitude: 7.43 },
      },
      {
        id: "evidence-2",
        kind: "sequence",
        node: "svc:checkout",
        text: "A slow inventory query preceded the checkout timeout in this recorded trace.",
        data: { trace_id: traceId, event_id: eventId(1) },
      },
      {
        id: "evidence-3",
        kind: "metric",
        node: "svc:inventory",
        text: "Connection pool wait time exceeded its normal range across 8 consecutive samples.",
        data: { samples: 8, confidence: 0.96 },
      },
    ],
  },
};
export const state = {
  scope: "observed",
  digest: "a531b98ca2759b85c97415677e334fdecab739e",
  state: {
    event_count: 64,
    endpoints: {
      "checkout /checkout": { count: 1320, errors: 12, duration_ms: 248.4 },
      "payments /charge": { count: 980, errors: 4, duration_ms: 187.2 },
      "inventory /stock": { count: 716, errors: 0, duration_ms: 312.6 },
    },
    edges: { "svc:checkout → svc:inventory": { calls: 1320, errors: 12 } },
    db_tables: { inventory: { reads: 716, writes: 124 } },
    cache: { "cache:catalog": { hits: 900, misses: 100 } },
    queues: { orders: { depth: 14 } },
    errors_by_type: { TimeoutError: 12 },
  },
};
export const graph = {
  nodes: [
    { id: "svc:gateway", anomalous: false, root_candidate: false },
    { id: "svc:checkout", anomalous: true, root_candidate: false },
    { id: "svc:payments", anomalous: false, root_candidate: false },
    { id: "svc:inventory", anomalous: true, root_candidate: false },
    { id: "db:inventory", anomalous: false, root_candidate: true },
    { id: "cache:catalog", anomalous: false, root_candidate: false },
  ],
  edges: [
    {
      source: "svc:gateway",
      target: "svc:checkout",
      calls: 4290,
      propagation: false,
    },
    {
      source: "svc:checkout",
      target: "svc:payments",
      calls: 3120,
      propagation: false,
    },
    {
      source: "svc:checkout",
      target: "svc:inventory",
      calls: 2230,
      propagation: true,
    },
    {
      source: "svc:inventory",
      target: "db:inventory",
      calls: 1980,
      propagation: true,
    },
    {
      source: "svc:inventory",
      target: "cache:catalog",
      calls: 360,
      propagation: false,
    },
  ],
};
export const settings = {
  tiering_enabled: false,
  hot_retention_days: 7,
  warm_retention_days: 90,
  lossy_sampling_enabled: false,
  llm_enabled: false,
  rag_enabled: true,
  services: ["checkout", "payments", "gateway", "inventory"],
};
export const simulation = {
  mode: "simulated",
  intervention: { type: "latency_scale", node: "db:inventory", factor: 0.5 },
  original: { error_rate: 0.023, p95_ms: 312.6, p99_ms: 684.2 },
  counterfactual: { error_rate: 0.009, p95_ms: 184.3, p99_ms: 372.1 },
  verdict: "Lower latency, fewer projected timeouts.",
  side_effects: {},
  assumptions: [
    "Recorded call structure and request volume remain unchanged.",
    "The intervention applies only to spans matched to the selected node.",
    "These projected outcomes are a simulation, not observed production behavior.",
  ],
  unsimulatable_count: 3,
  unsimulatable_percent: 4.7,
  input_digest: "a5b321fa221b132f84f25b4c",
  result_digest: "b63d80a567174b49f4682b84b256",
};
export function makeTrace(count = 64) {
  return {
    scope: "observed",
    trace_id: traceId,
    digest: "b51a877194472de591c1f9dd2a1",
    dict: {
      services: ["gateway", "checkout", "inventory", "payments"],
      types: ["http.request", "db.query", "http.client"],
    },
    spans: {
      id: Array.from({ length: count }, (_, i) => `span-${i}`),
      event_id: Array.from({ length: count }, (_, i) => eventId(i + 1)),
      parent: Array.from({ length: count }, (_, i) =>
        i === 0 ? null : i < 4 ? "span-0" : `span-${Math.floor((i - 1) / 3)}`,
      ),
      start_us: Array.from({ length: count }, (_, i) => i * 6000),
      dur_us: Array.from({ length: count }, (_, i) =>
        i === 0 ? count * 6500 : 15000 + (i % 7) * 11000,
      ),
      service_idx: Array.from({ length: count }, (_, i) => i % 4),
      type_idx: Array.from({ length: count }, (_, i) => i % 3),
      status: Array.from({ length: count }, (_, i) =>
        i === 10 || i === 19 ? "error" : "ok",
      ),
    },
  };
}
export async function mockWorkspace(
  page: Page,
  options: {
    authenticated?: boolean;
    empty?: boolean;
    error?: boolean;
    spans?: number;
  } = {},
) {
  if (options.authenticated !== false)
    await page.addInitScript(() =>
      sessionStorage.setItem("tracelore.token", "fixture-session"),
    );
  let resolved = false,
    sampled = false;
  const keys = [
    {
      key_hash: "a".repeat(64),
      name: "Checkout production",
      created_at: ago(5000),
      revoked_at: null as string | null,
    },
    {
      key_hash: "b".repeat(64),
      name: "Local development",
      created_at: ago(4000),
      revoked_at: ago(1000),
    },
  ];
  await page.routeWebSocket("**/api/ws/live", (socket) => {
    socket.onMessage(() =>
      socket.send(
        JSON.stringify(
          options.empty
            ? { ...live, per_service: {}, events_per_sec: 0 }
            : live,
        ),
      ),
    );
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname.replace(/^\/api/, ""),
      method = route.request().method();
    const fulfill = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    if (path === "/auth/token")
      return route.request().postDataJSON().secret === secret
        ? fulfill({
            access_token: "fixture-session",
            token_type: "bearer",
            expires_at: ago(-60),
          })
        : fulfill(
            {
              error: {
                code: "UNAUTHORIZED",
                message: "The dashboard secret is incorrect. Try again.",
              },
            },
            401,
          );
    if (path === "/incidents") {
      if (options.error)
        return fulfill(
          {
            error: {
              code: "UNAVAILABLE",
              message:
                "Telemetry is temporarily unavailable. Please try again.",
            },
          },
          503,
        );
      const list = options.empty
        ? []
        : incidents.map((item, i) =>
            i === 0 && resolved
              ? { ...item, status: "resolved", closed_at: ago(0) }
              : item,
          );
      const filtered = url.searchParams.get("status")
        ? list.filter((item) => item.status === url.searchParams.get("status"))
        : list;
      return fulfill({
        items: url.searchParams.has("cursor") ? filtered.slice(-2) : filtered,
        next_cursor:
          options.empty || url.searchParams.has("cursor")
            ? null
            : "next-fixture-page",
      });
    }
    if (/^\/incidents\/[^/]+\/resolve$/.test(path)) {
      resolved = true;
      return fulfill({
        ...incidents[0],
        status: "resolved",
        closed_at: ago(0),
      });
    }
    if (/^\/incidents\/[^/]+\/rca$/.test(path))
      return fulfill(options.empty ? null : rca);
    if (/^\/incidents\/[^/]+$/.test(path))
      return fulfill({
        ...incidents[0],
        status: resolved ? "resolved" : "open",
      });
    if (/^\/replay\/trace\/[^/]+\/state$/.test(path))
      return fulfill({
        ...state,
        digest: `${url.searchParams.get("event_id")}abcdefabcdefabcdef`,
        state: {
          ...state.state,
          event_count: Number(
            url.searchParams.get("event_id")?.slice(-12) ?? 64,
          ),
        },
      });
    if (/^\/replay\/trace\/[^/]+$/.test(path))
      return fulfill(makeTrace(options.spans));
    if (path === "/replay/state") return fulfill(state);
    if (path === "/graph")
      return fulfill(options.empty ? { nodes: [], edges: [] } : graph);
    if (path === "/settings")
      return fulfill({ ...settings, lossy_sampling_enabled: sampled });
    if (path === "/settings/sampling") {
      sampled = route.request().postDataJSON().enabled;
      return fulfill({ enabled: sampled });
    }
    if (path === "/settings/keys") {
      if (method === "POST") {
        const name = route.request().postDataJSON().name;
        keys.unshift({
          key_hash: "c".repeat(64),
          name,
          created_at: ago(0),
          revoked_at: null,
        });
        return fulfill({ name, key: "orr_fixture_only_not_a_real_key" });
      }
      return fulfill(options.empty ? [] : keys);
    }
    if (path.startsWith("/settings/keys/") && method === "DELETE") {
      const key = keys.find((item) => item.key_hash === path.split("/").pop())!;
      key.revoked_at = ago(0);
      return fulfill(key);
    }
    if (path === "/counterfactual") return fulfill(simulation);
    return fulfill(
      { error: { code: "NOT_FOUND", message: `Unmocked endpoint ${path}` } },
      404,
    );
  });
}
