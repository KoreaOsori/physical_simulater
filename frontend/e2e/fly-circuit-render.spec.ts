import { test, expect } from "@playwright/test";

/** Smoke test: the fly olfactory circuit page loads real data end to end
 * (REST fetch -> store -> r3f canvas) rather than just rendering a static
 * shell. Not a regression test for a specific past bug (unlike the worm
 * one) -- this circuit page has no documented history of breaking, so this
 * is baseline coverage in case a future refactor of the shared
 * FlyConnectomeCanvas/store breaks it. */
test("fly olfactory circuit page loads and renders its connectome", async ({ page }) => {
  await page.goto("/fly/olfactory");

  // FlyTopBar's connection-status text (see FlyTopBar.tsx) -- confirms the
  // /ws/fly/simulation socket actually connected, not just that the page
  // shell rendered.
  await expect(page.getByText("실시간 시뮬레이션")).toBeVisible({ timeout: 15_000 });
  // The r3f <canvas> only mounts once the ~2,452-neuron olfactory connectome
  // has actually loaded (see FlyConnectomeViewport's conditional render) --
  // a real fetch+parse cost, not instant, hence the longer timeout here.
  await expect(page.locator("canvas")).toBeVisible({ timeout: 15_000 });
});
