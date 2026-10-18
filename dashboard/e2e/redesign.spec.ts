import { test, expect } from "@playwright/test";
import { incidentId, traceId, mockWorkspace, secret } from "./ui-fixtures";

const viewports = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "laptop", width: 1366, height: 900 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 },
];
const routes = [
  ["incidents", "/incidents", "Incidents"],
  ["investigation", `/incidents/${incidentId}`, "checkout / inventory"],
  ["trace", `/traces/${traceId}`, "Trace explorer"],
  ["state", "/state", "Observed state"],
  ["dependencies", "/graph", "Dependencies"],
  ["what-if", "/counterfactual", "What-if lab"],
  ["incident-what-if", `/counterfactual?incident=${incidentId}`, "What-if lab"],
  ["settings", "/settings", "Settings"],
];

async function noOverflow(page: import("@playwright/test").Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
}
for (const viewport of viewports) {
  test(`visual route review · ${viewport.name}`, async ({ page }, info) => {
    test.setTimeout(90_000);
    await page.setViewportSize(viewport);
    await mockWorkspace(page);
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    for (const [name, path, heading] of routes) {
      await page.goto(path);
      await expect(
        page.getByRole("heading", { name: heading, level: 1 }),
      ).toBeVisible();
      await expect(page.getByLabel("Loading", { exact: true })).toHaveCount(0);
      if (name === "dependencies")
        await expect(page.locator(".react-flow__node")).toHaveCount(6);
      if (name === "incidents")
        await expect(page.locator("tbody tr")).toHaveCount(6);
      await page.evaluate(() => document.fonts.ready);
      await noOverflow(page);
      await page.screenshot({
        path: info.outputPath(`${name}.png`),
        fullPage: true,
        animations: "disabled",
      });
    }
    if (viewport.width <= 800)
      await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(
      page.getByLabel("Dashboard secret", { exact: true }),
    ).toBeVisible();
    await noOverflow(page);
    await page.screenshot({
      path: info.outputPath("login.png"),
      fullPage: true,
    });
    await page.goto("/page-that-does-not-exist");
    await expect(
      page.getByRole("heading", { name: "This page is out of view." }),
    ).toBeVisible();
    await noOverflow(page);
    await page.screenshot({
      path: info.outputPath("not-found.png"),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
}

test("login validation, successful sign-in, sign-out, and root redirect", async ({
  page,
}) => {
  await mockWorkspace(page, { authenticated: false });
  await page.goto("/");
  await expect(page).toHaveURL(/\/incidents$/);
  await page
    .getByLabel("Dashboard secret", { exact: true })
    .fill("incorrect-secret");
  await page.getByRole("button", { name: "Open observatory" }).click();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: /incorrect|end time after|temporarily unavailable/ }),
  ).toContainText("incorrect");
  await page.getByLabel("Dashboard secret", { exact: true }).fill(secret);
  const auth = page.waitForRequest(
    (request) =>
      request.url().endsWith("/api/auth/token") && request.method() === "POST",
  );
  await page.getByRole("button", { name: "Open observatory" }).click();
  expect((await auth).postDataJSON()).toEqual({ secret });
  await expect(
    page.getByRole("heading", { name: "Incidents", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  expect(
    await page.evaluate(() => sessionStorage.getItem("tracelore.token")),
  ).toBeNull();
});

test("search, status filtering, pagination and contextual reset", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.goto("/incidents");
  await expect(page.locator("tbody tr")).toHaveCount(6);
  await page
    .getByRole("textbox", { name: "Search incidents in this page" })
    .fill("inventory");
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page
    .getByRole("textbox", { name: "Search incidents in this page" })
    .fill("nothing-matches");
  await expect(page.getByText("No matching incidents")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByLabel("Filter incident status").selectOption("open");
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page.getByLabel("Filter incident status").selectOption("");
  await expect(page.locator("tbody tr")).toHaveCount(6);
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page.getByRole("button", { name: "Newest" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(6);
});

test("incident evidence → trace selection → keyboard scrub → state update", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.goto(`/incidents/${incidentId}`);
  await page.getByRole("button", { name: "View span" }).click();
  const cursor = page.getByLabel("Event cursor", { exact: true });
  await expect(cursor).toBeVisible();
  await cursor.focus();
  await cursor.press("Home");
  await cursor.press("ArrowRight");
  await expect(page.getByText("2 / 64", { exact: true })).toBeVisible();
  await expect(page.locator(".inspector-footer")).toContainText("events");
  await page.getByRole("tab", { name: "Endpoints", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Edges", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel")).toContainText("svc:checkout");
});

test("resolution cancel and save preserve the exact request payload", async ({
  page,
}, info) => {
  await mockWorkspace(page);
  await page.goto(`/incidents/${incidentId}`);
  await page
    .getByRole("button", { name: "Resolve incident", exact: true })
    .click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Record the verified resolution" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Resolve incident", exact: true })
    .click();
  await page
    .getByLabel("Root cause node", { exact: true })
    .fill("db:inventory");
  await page
    .getByLabel("Root cause", { exact: true })
    .fill("Slow inventory queries");
  await page
    .getByLabel("Resolution", { exact: true })
    .fill("Added the missing index.");
  await page.screenshot({
    path: info.outputPath("resolution-form.png"),
    fullPage: true,
  });
  const sent = page.waitForRequest((request) =>
    request.url().endsWith(`/api/incidents/${incidentId}/resolve`),
  );
  await page
    .getByRole("button", { name: "Save resolution", exact: true })
    .click();
  expect((await sent).postDataJSON()).toEqual({
    root_cause_node: "db:inventory",
    root_cause: "Slow inventory queries",
    resolution: "Added the missing index.",
  });
  await expect(page.getByText("Resolved", { exact: true })).toBeVisible();
});

test("timestamp replay and all inspector categories", async ({
  page,
}, info) => {
  await mockWorkspace(page);
  await page.goto("/state");
  await page
    .getByLabel("Point in time (your local timezone)")
    .fill("2026-10-18T10:30");
  const sent = page.waitForRequest((request) =>
    request.url().includes("/api/replay/state?"),
  );
  await page.getByRole("button", { name: "Reconstruct state" }).click();
  expect(new URL((await sent).url()).searchParams.get("at")).toBe(
    new Date("2026-10-18T10:30").toISOString(),
  );
  await expect(page.getByRole("tabpanel")).toContainText("checkout /checkout");
  for (const name of [
    "Edges",
    "Database tables",
    "Cache",
    "Queues",
    "Error types",
    "Endpoints",
  ]) {
    await page.getByRole("tab", { name, exact: true }).click();
    await expect(page.getByRole("tabpanel")).not.toContainText(
      "No observations",
    );
  }
  await page.screenshot({
    path: info.outputPath("reconstructed-state.png"),
    fullPage: true,
  });
});

for (const type of ["latency_scale", "timeout", "cache_hit_rate"]) {
  test(`simulation contract · ${type}`, async ({ page }, info) => {
    await mockWorkspace(page);
    await page.goto(`/counterfactual?incident=${incidentId}`);
    await page
      .getByRole("combobox", { name: "Intervention", exact: true })
      .selectOption(type);
    const intervention =
      type === "latency_scale"
        ? { type, node: "db:inventory", factor: 0.5 }
        : type === "timeout"
          ? {
              type,
              caller: "svc:checkout",
              callee: "svc:payments",
              new_timeout_ms: 2000,
            }
          : {
              type,
              service: "catalog",
              route: "/products/{id}",
              target_hit_rate: 0.9,
            };
    if (type === "latency_scale")
      await page.getByLabel("Node", { exact: true }).fill("db:inventory");
    if (type === "timeout") {
      await page.getByLabel("Caller service").fill("svc:checkout");
      await page.getByLabel("Callee service").fill("svc:payments");
    }
    if (type === "cache_hit_rate") {
      await page.getByLabel("Service", { exact: true }).fill("catalog");
      await page.getByLabel("Route template").fill("/products/{id}");
    }
    const sent = page.waitForRequest((request) =>
      request.url().endsWith("/api/counterfactual"),
    );
    await page.getByRole("button", { name: "Run simulation" }).click();
    expect((await sent).postDataJSON()).toEqual({
      incident_id: incidentId,
      intervention,
    });
    await expect(
      page.getByText("Lower latency, fewer projected timeouts.", {
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByText("Assumptions & limits", { exact: true }),
    ).toBeVisible();
    await noOverflow(page);
    await page.screenshot({
      path: info.outputPath(`simulation-${type}.png`),
      fullPage: true,
    });
  });
}

test("invalid simulation window stays local; valid window uses the original contract", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.goto("/counterfactual");
  await page.getByLabel("Node", { exact: true }).fill("db:inventory");
  await page.getByLabel("Window start (local)").fill("2026-10-18T10:30");
  await page.getByLabel("Window end (local)").fill("2026-10-18T09:30");
  await page.getByRole("button", { name: "Run simulation" }).click();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: /incorrect|end time after|temporarily unavailable/ }),
  ).toContainText("end time after");
  await page.getByLabel("Window end (local)").fill("2026-10-18T11:30");
  const sent = page.waitForRequest((request) =>
    request.url().endsWith("/api/counterfactual"),
  );
  await page.getByRole("button", { name: "Run simulation" }).click();
  expect((await sent).postDataJSON()).toEqual({
    window: {
      start: new Date("2026-10-18T10:30").toISOString(),
      end: new Date("2026-10-18T11:30").toISOString(),
    },
    intervention: { type: "latency_scale", node: "db:inventory", factor: 0.5 },
  });
});

test("key creation, copy, dismissal, revoke confirmation and sampling", async ({
  page,
  context,
}, info) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await mockWorkspace(page);
  await page.goto("/settings");
  await page
    .getByLabel("Key name", { exact: true })
    .fill("Inventory production");
  const created = page.waitForRequest(
    (request) =>
      request.url().endsWith("/api/settings/keys") &&
      request.method() === "POST",
  );
  await page.getByRole("button", { name: "Create key" }).click();
  expect((await created).postDataJSON()).toEqual({
    name: "Inventory production",
  });
  await page.getByRole("button", { name: "Copy key" }).click();
  await expect(
    page.getByRole("button", { name: "Copied", exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    "orr_fixture_only_not_a_real_key",
  );
  await page.screenshot({
    path: info.outputPath("new-key.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Dismiss new key" }).click();
  await expect(
    page.getByText("orr_fixture_only_not_a_real_key", { exact: true }),
  ).toHaveCount(0);
  const row = page
    .locator(".key-row")
    .filter({ hasText: "Inventory production" });
  await row.getByRole("button", { name: "Revoke", exact: true }).click();
  await row.getByRole("button", { name: "Cancel", exact: true }).click();
  await row.getByRole("button", { name: "Revoke", exact: true }).click();
  const revoked = page.waitForRequest(
    (request) =>
      request.method() === "DELETE" &&
      request.url().includes("/api/settings/keys/"),
  );
  await row.getByRole("button", { name: "Confirm revoke" }).click();
  expect((await revoked).url()).toContain("c".repeat(64));
  await expect(row.getByText("Revoked", { exact: true })).toBeVisible();
  const sampled = page.waitForRequest((request) =>
    request.url().endsWith("/api/settings/sampling"),
  );
  await page
    .getByRole("switch", { name: "Summarized analytics", exact: true })
    .click();
  expect((await sampled).postDataJSON()).toEqual({ enabled: true });
  await expect(page.getByRole("switch")).toBeChecked();
});

test("mobile drawer focus, escape, route changes, and reachable sign-out", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockWorkspace(page);
  await page.goto("/incidents");
  const menu = page.getByRole("button", { name: "Open navigation" });
  await menu.click();
  const drawer = page.getByRole("dialog", { name: "Workspace navigation" });
  await expect(drawer).toBeVisible();
  await drawer.getByRole("button", { name: "Sign out", exact: true }).focus();
  await page.keyboard.press("Tab");
  await expect(
    drawer.getByRole("link", { name: "Tracelore home" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toBeFocused();
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await menu.click();
  await drawer.getByRole("link", { name: "Dependencies", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Dependencies", exact: true }),
  ).toBeVisible();
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await menu.click();
  await drawer.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByLabel("Dashboard secret", { exact: true }),
  ).toBeVisible();
});

test("empty and failure states remain usable", async ({ page }, info) => {
  await mockWorkspace(page, { empty: true });
  await page.goto("/incidents");
  await expect(
    page.getByText("All quiet, so far.", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("empty-incidents.png"),
    fullPage: true,
  });
  await page.goto("/graph");
  await expect(
    page.getByText("Your map starts with a call", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("empty-graph.png"),
    fullPage: true,
  });
  await page.route("**/api/incidents?**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "UNAVAILABLE",
          message: "Telemetry is temporarily unavailable. Please try again.",
        },
      }),
    }),
  );
  await page.goto("/incidents");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: /incorrect|end time after|temporarily unavailable/ }),
  ).toContainText("temporarily unavailable");
  await expect(
    page.getByRole("button", { name: "Try again", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("error-incidents.png"),
    fullPage: true,
  });
});

test("an expired session returns to the dashboard sign-in", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.route("**/api/incidents?**", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "UNAUTHORIZED", message: "Session expired" },
      }),
    }),
  );
  await page.goto("/incidents");
  await expect(
    page.getByLabel("Dashboard secret", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => sessionStorage.getItem("tracelore.token")),
  ).toBeNull();
});

test("10,000-span waterfall remains within the existing frame budget", async ({
  page,
}) => {
  await mockWorkspace(page, { spans: 10_000 });
  await page.goto(`/traces/${traceId}`);
  await expect(page.getByLabel("Event cursor", { exact: true })).toBeVisible();
  const samples = await page.evaluate(async () => {
    const scroller = document.querySelector<HTMLDivElement>(".timeline-wrap")!,
      canvas = scroller.querySelector<HTMLCanvasElement>("canvas")!,
      result: number[] = [];
    for (let n = 0; n < 30; n++) {
      scroller.scrollTop = ((n % 20) / 19) * scroller.scrollHeight;
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      );
      result.push(Number(canvas.dataset.drawMs));
    }
    return result.sort((a, b) => a - b);
  });
  expect(samples.every(Number.isFinite)).toBe(true);
  expect(samples[Math.floor(samples.length * 0.95)]).toBeLessThan(16);
});

test("320px layouts and mobile replay controls remain usable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await mockWorkspace(page);
  for (const [, path, heading] of routes) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: heading, level: 1 }),
    ).toBeVisible();
    await expect(page.getByLabel("Loading", { exact: true })).toHaveCount(0);
    await noOverflow(page);
  }
  await page.goto(`/traces/${traceId}`);
  const cursor = page.getByLabel("Event cursor", { exact: true });
  await cursor.focus();
  await cursor.press("ArrowRight");
  await expect(page.locator(".trace-mobile")).toBeVisible();
  await expect(page.getByRole("button", { name: "Zoom in" })).not.toBeVisible();
  await expect(
    page.getByText(
      "Tap a span or use the event cursor to inspect its recorded state.",
    ),
  ).toBeVisible();
});

test("dependency map overview renders all nodes and its controls work", async ({
  page,
}, info) => {
  await mockWorkspace(page);
  await page.goto("/graph");
  await expect(page.locator(".react-flow__node")).toHaveCount(6);
  await expect(page.locator(".react-flow__minimap-node")).toHaveCount(6);
  await page.getByRole("button", { name: /zoom in/i }).click();
  await page.getByRole("button", { name: /fit view/i }).click();
  await page.setViewportSize({ width: 768, height: 1024 });
  await noOverflow(page);
  await page.screenshot({
    path: info.outputPath("graph-overview-tablet.png"),
    fullPage: true,
  });
});
