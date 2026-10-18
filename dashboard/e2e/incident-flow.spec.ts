import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(readFileSync("../artifacts/e2e.json", "utf8")) as {
  incident_id: string;
  trace_id: string;
  secret: string;
};
test("incident → concrete evidence → scrub → observed-state update", async ({
  page,
}) => {
  await page.goto("/incidents");
  await page.getByLabel("Dashboard secret").fill(fixture.secret);
  await page.getByRole("button", { name: "Open observatory →" }).click();
  await page.goto(`/incidents/${fixture.incident_id}`);
  await expect(
    page.getByRole("heading", { name: "Root-cause assessment" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "View span ↗" }).first().click();
  await expect(page.getByLabel("Event cursor")).toBeVisible();
  await page.getByLabel("Event cursor").focus();
  await page.getByLabel("Event cursor").press("Home");
  await page.getByLabel("Event cursor").press("ArrowRight");
  await expect(page.getByText(/2 \/ 10000/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "State inspector" }),
  ).toBeVisible();
  await expect(page.getByText(/digest /).last()).toBeVisible();
});
test("10,000 spans scrub within the measured frame budget", async ({
  page,
}) => {
  await page.goto("/incidents");
  await page.getByLabel("Dashboard secret").fill(fixture.secret);
  await page.getByRole("button", { name: "Open observatory →" }).click();
  await page.goto(`/traces/${fixture.trace_id}`);
  await expect(page.getByLabel("Event cursor")).toBeVisible();
  const frames = await page.evaluate(async () => {
    const samples: number[] = [];
    const scroller = document.querySelector<HTMLDivElement>(".timeline-wrap")!;
    const canvas = scroller.querySelector<HTMLCanvasElement>("canvas")!;
    for (let index = 0; index < 60; index++) {
      scroller.scrollTop = ((index % 20) / 19) * scroller.scrollHeight;
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => resolve()),
      );
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => resolve()),
      );
      samples.push(Number(canvas.dataset.drawMs));
    }
    return samples.sort((a, b) => a - b);
  });
  expect(frames.every(Number.isFinite)).toBe(true);
  expect(frames[Math.floor(frames.length * 0.95)]).toBeLessThan(16);
});
