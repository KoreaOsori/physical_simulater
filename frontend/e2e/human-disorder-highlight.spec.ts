import { test, expect } from "@playwright/test";

/**
 * Pins docs/21-human-macro-disorder-associations.md's own worked example:
 * clicking "대뇌색맹" (cerebral achromatopsia) on the Vis network should
 * select it and show its description inline (the accordion pattern doc21
 * switched to after finding the original fixed-position panel overlapped).
 * Does NOT assert the 3D scene's red-highlight count (Vis_1/Vis_4, 2
 * regions) -- that lives inside the WebGL canvas, out of reach for a
 * DOM-level test; this covers the fetch -> render -> click -> selection
 * state chain instead.
 */
test("selecting a disorder on the human macro page shows its description", async ({ page }) => {
  await page.goto("/human/connectome/macro");

  const disorderButton = page.getByRole("button", { name: "대뇌색맹 (Cerebral Achromatopsia)" });
  await expect(disorderButton).toBeVisible({ timeout: 15_000 });

  await disorderButton.click();
  await expect(disorderButton).toHaveAttribute("aria-pressed", "true");

  const detail = page.locator(".disorder-detail");
  await expect(detail).toBeVisible();
  await expect(detail).not.toBeEmpty();

  // Clicking again deselects (same button, same accordion) -- the
  // toggle-off path doc21 relies on for "clicking a different disorder
  // swaps the description" also needs the off path to work.
  await disorderButton.click();
  await expect(disorderButton).toHaveAttribute("aria-pressed", "false");
  await expect(detail).toBeHidden();
});
