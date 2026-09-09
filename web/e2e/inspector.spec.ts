import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

test("app loads a sufficient context bundle", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("sufficiency")).toContainText("SUFFICIENT", {
    timeout: 20_000,
  });
  await expect(page.getByTestId("assembled-question")).toContainText("j4-military-s");
  await expect(page.getByTestId("objects")).toBeVisible();
  await expect(page.getByTestId("relationships")).toBeVisible();
  await expect(page.getByTestId("facts")).toBeVisible();
  await expect(page.getByTestId("metrics")).toBeVisible();
  await expect(page.getByTestId("history")).toBeVisible();
  await expect(page.getByTestId("provenance")).toBeVisible();
  await page.screenshot({
    path: path.join(root, "docs/screenshots/context-inspector.png"),
    fullPage: true,
  });
});

test("insufficient case makes missing context obvious", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("question-input").fill("Should I reprice stone-cargo-l?");
  await page.getByRole("button", { name: "Assemble" }).click();
  await expect(page.getByTestId("sufficiency")).toContainText("INSUFFICIENT");
  await expect(page.getByTestId("missing-context")).toBeVisible();
  await expect(page.getByTestId("missing-context")).toContainText("listing");
});

test("item drill-down shows state, listings, timeline", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("sufficiency")).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Object" }).click();
  await page.getByTestId("sku-input").fill("j4-military-s");
  await page.getByRole("button", { name: "Load" }).click();
  await expect(page.getByTestId("item-view")).toBeVisible();
  await expect(page.getByTestId("item-state")).toContainText("j4-military-s");
  await expect(page.getByTestId("item-timeline")).toBeVisible();
});

test("evaluation reports all 20 cases", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Evaluation" }).click();
  await expect(page.getByTestId("eval-summary")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("eval-total")).toHaveText("20");
  await expect(page.getByTestId("eval-pass")).toHaveText("20");
  await expect(page.getByTestId("eval-fail")).toHaveText("0");
  await expect(page.getByTestId("eval-skip")).toHaveText("0");
});

test("temporal as-of question is sufficient", async ({ page }) => {
  await page.goto("/");
  await page
    .getByTestId("question-input")
    .fill("What was the active listing state for j4-military-s two weeks ago?");
  await page.getByRole("button", { name: "Assemble" }).click();
  await expect(page.getByTestId("sufficiency")).toContainText("SUFFICIENT");
  await expect(page.getByTestId("facts")).toContainText("listing_as_of");
});
