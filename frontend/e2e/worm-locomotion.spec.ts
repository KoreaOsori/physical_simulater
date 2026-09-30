import { test, expect } from "@playwright/test";

/**
 * Regression test for the exact bug docs/17-worm-rft-locomotion.md found
 * only by manual browser testing: OrbitControls damping + a reactive
 * `target` prop fighting the per-frame pose update caused the worm to drift
 * off screen during a sustained "forward" command. That fix removed the
 * `target` prop and set `enableDamping={false}` -- this test pins the
 * observable behavior (camera keeps the worm near center; position actually
 * changes) so a future change can't silently reintroduce it.
 *
 * Timing note: a command doesn't move the worm instantly -- it schedules a
 * 10s staggered COMMAND->SYNAPSE->NT->MUSCLE->MOVEMENT playback (see
 * features/simulation-control/lib/playback.ts's TOTAL_SEQUENCE_MS=10000),
 * and only the MOVEMENT stage near the end actually drives the physics this
 * test reads. Discovering that timing (this test's first run pressed
 * ArrowUp on a 700ms cadence and saw ~zero displacement) is itself the kind
 * of thing only running the real thing catches -- consistent with docs/17's
 * own experience.
 */
test("worm stays trackable and actually moves after a forward command completes", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("실시간 시뮬레이션")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator("canvas")).toBeVisible();
  await page.waitForFunction(() => Boolean((window as unknown as { __wormPose?: object }).__wormPose), { timeout: 15_000 });

  const readPose = () =>
    page.evaluate(() => {
      const pose = (window as unknown as { __wormPose: { x: number; z: number } }).__wormPose;
      return { x: pose.x, z: pose.z };
    });

  const before = await readPose();

  await page.keyboard.press("ArrowUp");
  // Poll for actual displacement instead of a fixed sleep: the ~9.85s
  // (7.65s stage delay + 2.2s pulse, see playback.ts) is a floor, not a
  // guarantee, under host CPU contention (setTimeout/rAF can lag on a busy
  // machine -- this repo's dev box also runs unrelated heavy background
  // containers). A generous 25s ceiling still fails fast if locomotion is
  // truly broken, but doesn't flake just because the host was briefly busy.
  await page
    .waitForFunction(
      (beforePose) => {
        const pose = (window as unknown as { __wormPose?: { x: number; z: number } }).__wormPose;
        if (!pose) return false;
        return Math.hypot(pose.x - beforePose.x, pose.z - beforePose.z) > 0.5;
      },
      before,
      { timeout: 25_000, polling: 250 },
    )
    .catch(() => {}); // let the explicit assertion below produce the real failure message

  const after = await readPose();
  const displacement = Math.hypot(after.x - before.x, after.z - before.z);

  // It actually moved (locomotion is live, not stuck at rest)...
  expect(displacement).toBeGreaterThan(0.5);
  // ...but stayed in a plausible on-screen range rather than flying off
  // (docs/17's bug: the worm ended up far outside the camera's reach).
  // RFT_SPEED_SCALE=2.5 (docs/22) implies single-digit body-lengths of
  // travel from one command, not hundreds of scene units.
  expect(Math.abs(after.x)).toBeLessThan(80);
  expect(Math.abs(after.z)).toBeLessThan(80);

  // The canvas itself is still rendering (no crash/blank screen).
  await expect(page.locator("canvas")).toBeVisible();
});
