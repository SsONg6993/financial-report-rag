import { expect, test } from "@playwright/test";

test("V3.2 Home has a concise evidence hierarchy", async ({ page }) => {
  await page.goto("/");
  for (const heading of [
    "Market Overview",
    "My Watchlist",
    "Top Intelligence Highlights",
    "Institutional Activity",
    "Quick Research",
  ]) {
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
  }
  await expect(
    page.getByRole("heading", { name: "Interesting Ideas" }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/v32-home-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("Home empty states stay useful without inventing activity", async ({
  page,
}) => {
  await page.route("**/api/home/feed", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({
      response,
      json: { ...data, market_overview: [], watchlist: [], activity: [] },
    });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "Saved market quotes are not available",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("No companies saved yet.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("No comparable saved institutional changes", {
      exact: false,
    }),
  ).toBeVisible();
});

test("Intelligence feed filters concise dated cards", async ({ page }) => {
  await page.goto("/intelligence");
  await expect(
    page
      .getByRole("heading", { name: "Intelligence Feed", exact: true })
      .first(),
  ).toBeVisible();
  await page
    .getByPlaceholder("Search company, manager, or source…")
    .fill("AAPL");
  await expect(page.getByText(/Published\/filed/).first()).toBeVisible();
  await page.getByRole("button", { name: "My watchlist", exact: true }).click();
  await expect(
    page.getByText(/Watchlist priority|Relevant/).first(),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/v32-intelligence-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("UNH keeps filing research useful when market quotes are missing", async ({
  page,
}) => {
  await page.goto("/research/UNH");
  await expect(
    page.getByRole("heading", {
      name: "UnitedHealth Group Incorporated",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Health Care", { exact: false }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Market data availability", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Business Overview", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/health care and well-being company/i),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Latest important filing", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Quote updated/)).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/v32-unh-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("research section navigation remains usable on narrow screens", async ({
  page,
}) => {
  await page.goto("/research/UNH");
  const navigation = page.getByRole("navigation", {
    name: "Company research sections",
  });
  await expect(
    navigation.getByRole("link", { name: "Financials", exact: true }),
  ).toBeVisible();
  await navigation
    .getByRole("link", { name: "Institutional ownership", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Institutional Ownership", exact: true }),
  ).toBeVisible();
});

test("Ask routes a UNH filing question to grounded research", async ({
  page,
}) => {
  await page.goto("/ask");
  await page
    .getByLabel("What would you like to investigate?")
    .fill("What changed in UNH's latest filing?");
  await page
    .getByRole("button", { name: "Ask ThesisLens", exact: true })
    .click();
  const response = page.getByRole("article");
  await expect(
    response.getByRole("heading", {
      name: "What the evidence supports",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    response.getByText(/AAPL|Apple financial statements/i),
  ).toHaveCount(0);
  await expect(response.getByText(/Sources & evidence/)).toBeVisible();
});
