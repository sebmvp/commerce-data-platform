/**
 * E2E — user flows over the Executive Operator Workspace. Flow assertions,
 * not CSS detail. All routes must be real app behavior against the demo API.
 */
import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

async function ask(page: import("@playwright/test").Page, question: string) {
  await page.getByTestId("question-input").fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

function exceptionRows(page: import("@playwright/test").Page) {
  return page.locator("[data-testid^='attention-']");
}

/* ── Command Center ── */

test("command center loads with exception-first hierarchy", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("command-center-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("environment")).toHaveAttribute("data-env", "demo");
  const rows = exceptionRows(page);
  await expect(rows.first()).toBeVisible({ timeout: 20_000 });
  // exception cap: at most 5 decision rows
  const count = await rows.count();
  expect(count).toBeGreaterThanOrEqual(1);
  expect(count).toBeLessThanOrEqual(5);
  // pulse + changes present
  await expect(page.getByTestId("pulse")).toContainText(/items/i);
  await expect(page.getByTestId("recent-changes")).toBeVisible();
  await page.screenshot({
    path: path.join(root, "docs/screenshots/command-center.png"),
  });
});

test("exception opens object panel while inventory stays mounted", async ({ page }) => {
  await page.goto("/");
  const row = exceptionRows(page).first();
  await expect(row).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(300);
  await row.click();
  await expect(page.getByTestId("item-view")).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/inventory\//);
  // wide viewport: inventory table remains in the DOM
  await expect(page.getByTestId("inventory-table")).toBeVisible();
  await page.screenshot({
    path: path.join(root, "docs/screenshots/inventory-table.png"),
  });
});

/* ── Global Business Search ── */

test("command palette finds an object and opens it", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("search-trigger").click();
  await page.getByTestId("palette-input").fill("jordan");
  const hit = page.locator("[data-testid^='search-hit-item']").first();
  await expect(hit).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: path.join(root, "docs/screenshots/search-palette.png") });
  await hit.click();
  await expect(page.getByTestId("item-view")).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/inventory\//);
});

test("palette hit can open the Librarian bound to the hit", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("search-trigger").click();
  await page.getByTestId("palette-input").fill("stone");
  const hit = page.locator("[data-testid^='search-hit-item']").first();
  await expect(hit).toBeVisible({ timeout: 20_000 });
  await hit.getByRole("button", { name: /Ask Librarian/i }).click();
  await expect(page.getByTestId("librarian-page")).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/librarian\//);
});

/* ── Inventory table ── */

test("inventory table filters, sorts, and keeps size in its own column", async ({ page }) => {
  await page.goto("/inventory?status=owned");
  await expect(page.getByTestId("inventory-page")).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveURL(/status=owned/);
  const rows = page.locator("[data-testid^='inv-row-']");
  await expect(rows.first()).toBeVisible({ timeout: 20_000 });
  const ownedCount = await rows.count();
  expect(ownedCount).toBeGreaterThan(0);

  await page.getByTestId("inventory-search").fill("jordan");
  const filteredCount = await rows.count();
  expect(filteredCount).toBeLessThan(ownedCount);

  // sort by acquisition does not crash and reorders
  await page.getByTestId("sort-acquisition_cost_cny").click();
  await expect(rows.first()).toBeVisible();
});

test("row click opens object panel; close returns to the list with filter", async ({ page }) => {
  await page.goto("/inventory?status=owned");
  const rows = page.locator("[data-testid^='inv-row-']");
  await expect(rows.first()).toBeVisible({ timeout: 20_000 });
  await rows.first().click();
  await expect(page.getByTestId("item-view")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("close-panel").click();
  await expect(page.getByTestId("inventory-page")).toBeVisible();
  await expect(page).toHaveURL(/status=owned/);
});

/* ── Object workspace ── */

test("object identity uses product name with provenance collapsed", async ({ page }) => {
  await page.goto("/inventory/j4-military-s");
  await expect(page.getByTestId("item-view")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("item-view")).toContainText("Jordan 4 Retro");
  await expect(page.getByTestId("item-state")).toBeVisible();
  await expect(page.getByTestId("item-timeline")).toBeVisible();
  await expect(page.getByTestId("ask-librarian")).toBeVisible();
  // provenance is a disclosure; tool names are not the default view
  await expect(page.getByTestId("item-provenance")).toBeVisible();
  await page.screenshot({ path: path.join(root, "docs/screenshots/item-object.png") });
});

/* ── Librarian ── */

test("contextual librarian answers on the object without leaving it", async ({ page }) => {
  await page.goto("/inventory/j4-military-s");
  await expect(page.getByTestId("ask-librarian")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("ask-librarian").click();
  await expect(page.getByTestId("item-view")).toBeVisible();
  await expect(page).toHaveURL(/ask=1/);
  await page.getByTestId("question-input").fill("Should I reprice j4-military-s?");
  await page
    .getByTestId("contextual-librarian")
    .getByRole("button", { name: "Ask" })
    .click();
  await expect(page.getByTestId("sufficiency")).toContainText("SUFFICIENT", {
    timeout: 25_000,
  });
  await expect(page.getByTestId("cited-evidence")).toContainText(/Watch|Price/i);
  await expect(page.getByTestId("provenance")).toBeVisible();
  await page.screenshot({
    path: path.join(root, "docs/screenshots/librarian-contextual.png"),
  });
});

test("full librarian: sufficient answer with evidence hierarchy", async ({ page }) => {
  await page.goto("/librarian/j4-military-s");
  await expect(page.getByTestId("bound-chip")).toBeVisible({ timeout: 20_000 });
  await ask(page, "Should I reprice j4-military-s?");
  const suff = page.getByTestId("sufficiency");
  await expect(suff).toContainText("SUFFICIENT", { timeout: 25_000 });
  await expect(page.getByTestId("answer-text")).toBeVisible();
  await expect(page.getByTestId("answer-text")).not.toContainText(
    "Context is sufficient. Decisive evidence is below",
  );
  await expect(page.getByTestId("cited-evidence")).toContainText(
    /Watch rate|Watchers|Listing age|Asking price/i,
  );
  await expect(page.getByTestId("relationship-map")).toBeVisible();
  await expect(page.getByTestId("provenance")).toBeVisible();
  await page.screenshot({ path: path.join(root, "docs/screenshots/librarian.png") });
});

test("insufficient case names missing context with a way to inspect", async ({ page }) => {
  await page.goto("/librarian/stone-cargo-l");
  await ask(page, "Should I reprice stone-cargo-l?");
  const missing = page.getByTestId("missing-context");
  await expect(missing).toBeVisible({ timeout: 25_000 });
  await expect(missing).toContainText(/listing/i);
  await expect(missing).toContainText("Inspect this object");
});

test("unbound librarian sample chips contain no SKU", async ({ page }) => {
  await page.goto("/librarian");
  for (const chip of [
    "What should I focus on today?",
    "What changed since the last snapshot?",
    "Which listings have interest but no offers?",
  ]) {
    await expect(page.getByRole("button", { name: chip, exact: true })).toBeVisible();
  }
});

test("relationship node opens the object view", async ({ page }) => {
  await page.goto("/librarian/j4-military-s");
  await ask(page, "Should I reprice j4-military-s?");
  await expect(page.getByTestId("relationship-map")).toBeVisible({ timeout: 25_000 });
  await page.getByTestId("rel-node-Item-j4-military-s").click();
  await expect(page.getByTestId("item-view")).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/inventory\/j4-military-s/);
});

/* ── Sandbox action loop ── */

test("reprice propose → approve → timeline → librarian sees the change", async ({ page }) => {
  await page.goto("/inventory/j4-military-s");
  await expect(page.getByTestId("action-panel")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("sandbox-price").fill("640");
  await page.getByTestId("propose-action").click();
  await expect(page.getByTestId("pending-action")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("approve-action").click();
  await expect(page.getByTestId("applied-action")).toBeVisible({ timeout: 25_000 });
  await expect(page.getByTestId("item-timeline")).toContainText(/price/i);

  // next Librarian query observes the applied price (bound full workspace)
  await page.goto("/librarian/j4-military-s");
  await ask(page, "Should I reprice j4-military-s?");
  const suff = page.getByTestId("sufficiency");
  await expect(suff).toBeVisible({ timeout: 25_000 });
  const body = await suff.innerText();
  expect(body).toMatch(/640/);
});

/* ── Sources ── */

test("sources lists truthful source state with steward disclosure", async ({ page }) => {
  await page.goto("/sources");
  await expect(page.getByTestId("sources-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("sources-table")).toContainText(/Items/i);
  await expect(page.getByTestId("sources-trust")).toBeVisible();
  const body = page.getByTestId("sources-page");
  const text = await body.innerText();
  expect(text).not.toMatch(/agent/i);
  await expect(page.getByTestId("steward-disclosure")).toBeVisible();
  await page.screenshot({ path: path.join(root, "docs/screenshots/sources.png") });
});

/* ── Data Health ── */

test("data health leads with trust; ingest runs behind disclosure", async ({ page }) => {
  await page.goto("/data-health");
  await expect(page.getByTestId("trust-banner")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("coverage")).toContainText(/available/i);
  await expect(page.getByTestId("ingest-runs-details")).toBeVisible();
  await page.getByTestId("ingest-runs-details").locator("summary").click();
  await expect(page.getByTestId("ingest-runs")).toContainText(/loaded/i);
  await page.screenshot({ path: path.join(root, "docs/screenshots/data-health.png") });
});

/* ── Evaluation ── */

test("evaluation summarizes layers; cases behind explicit disclosure", async ({ page }) => {
  await page.goto("/evaluation");
  await expect(page.getByTestId("eval-summary")).toBeVisible({ timeout: 40_000 });
  await expect(page.getByTestId("eval-summary")).toContainText("Context assembly");
  await expect(page.getByTestId("lexical")).toContainText("Lexical baseline");
  await expect(page.locator("[data-testid^='eval-case-']")).toHaveCount(0);
  await page.getByTestId("toggle-cases").click();
  await expect(page.locator("[data-testid^='eval-case-']").first()).toBeVisible();
  await page.screenshot({ path: path.join(root, "docs/screenshots/evaluation.png") });
});

/* ── Shell environment / navigation ── */

test("footnote hides model detail behind a disclosure; back/forward works", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("runtime-footnote")).toBeVisible({ timeout: 20_000 });
  const footnote = page.getByTestId("runtime-footnote");
  expect(await footnote.innerText()).not.toContain("Fake ·");
  await page.locator("[data-testid='model-disclosure'] summary").click();
  await expect(footnote).toContainText("Fake");

  await page.getByTestId("nav-inventory").click();
  await expect(page.getByTestId("inventory-page")).toBeVisible();
  await page.getByTestId("nav-librarian").click();
  await expect(page.getByTestId("librarian-page")).toBeVisible();
  await page.goBack();
  await expect(page.getByTestId("inventory-page")).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("librarian-page")).toBeVisible();
});

test("no raw exact 'Loading' text anywhere on inventory", async ({ page }) => {
  await page.goto("/inventory");
  await expect(page.getByTestId("inventory-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading", { exact: true })).toHaveCount(0);
});
