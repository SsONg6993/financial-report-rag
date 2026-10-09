import { test, expect } from "@playwright/test";

for (const [name, ticker, company] of [
  ["Tesla", "TSLA", "Tesla, Inc."],
  ["Keysight", "KEYS", "Keysight Technologies, Inc."],
] as const) {
  test(`SEC company search resolves ${name} to ${ticker}`, async ({ page }) => {
    await page.goto("/research");
    const search = page.getByRole("search");
    await search
      .getByRole("textbox", { name: "Search companies, investors, or tickers" })
      .fill(name);
    await expect(
      search.getByRole("button", { name: new RegExp(company) }),
    ).toBeVisible();
    await search.getByRole("button", { name: new RegExp(company) }).click();
    await expect(page).toHaveURL(new RegExp(`/research/${ticker}$`));
    await expect(
      page.getByRole("heading", { name: company, exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: `test-results/company-${ticker.toLowerCase()}-${test.info().project.name}.png`,
      fullPage: true,
    });
  });
}

test("light mode is optional and persists during navigation", async ({
  page,
}) => {
  await page.goto("/research/AAPL");
  await page.getByRole("button", { name: "Switch to light mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("link", { name: "Discover", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(
    page.getByRole("heading", { name: "Featured investors" }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/discover-light-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("rendered disclosure context and viewport layout", async ({ page }) => {
  await page.goto("/research/AAPL");
  await page
    .getByRole("heading", { name: "Ideas to Track", exact: true })
    .scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `test-results/research-viewport-${test.info().project.name}.png`,
  });
  await page
    .getByText("Advanced tracking, disclosures, and source details", {
      exact: true,
    })
    .click();
  await page
    .getByText("Insider activity · SEC Form 4", { exact: true })
    .click();
  await expect(
    page
      .getByRole("heading", { name: "Newstead Jennifer", exact: true })
      .first(),
  ).toBeVisible();
  await expect(page.getByText(/Transaction code S/).first()).toBeVisible();
  await page.screenshot({
    path: `test-results/disclosures-${test.info().project.name}.png`,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("real Home and Discover have dated disclosure data", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Top Investor Activity" }),
  ).toBeVisible();
  await expect(page.getByText("SEC Form 13F").first()).toBeVisible();
  await page.screenshot({
    path: `test-results/home-${test.info().project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: "Discover", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Featured investors" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Berkshire Hathaway", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Coatue Management", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/discover-${test.info().project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("portfolio network compares stored disclosures and supports interaction", async ({
  page,
}) => {
  await page.goto("/discover");
  await expect(
    page.getByRole("heading", { name: "Institutional Portfolio Network" }),
  ).toBeVisible();
  const canvas = page.getByTestId("portfolio-network-canvas");
  await expect(canvas).toBeVisible();
  await expect(page.getByText("Common to all")).toBeVisible();
  await page
    .getByText("Definitions, source coverage, and position changes")
    .click();
  await expect(
    page.getByText(/13F filings are delayed and incomplete/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.getByRole("button", { name: "Reset view" }).click();
  await expect(
    page.getByRole("table", { name: "Pairwise Jaccard similarity heatmap" }),
  ).toBeVisible();
  const node = canvas
    .getByRole("button", { name: /Select .* portfolio node/ })
    .first();
  await node.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("complementary", { name: "Selected network node details" }),
  ).toBeVisible();
  await page.getByPlaceholder("Filter company or ticker").fill("AAPL");
  await expect(
    page.getByRole("button", { name: "Clear company filter" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear company filter" }).click();
  const period = page.getByRole("combobox", { name: "Reporting date" });
  await period.selectOption("2026-03-31");
  await expect(period).toHaveValue("2026-03-31");
  await page.screenshot({
    path: `test-results/portfolio-network-${test.info().project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("portfolio network honors reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/discover");
  await expect(
    page.getByRole("button", { name: "Play historical timeline" }),
  ).toBeDisabled();
  await expect(
    page.getByText("Playback disabled for reduced motion"),
  ).toBeVisible();
});
test("Berkshire to AAPL to tracking and evaluation persists", async ({
  page,
}) => {
  await page.goto("/discover/berkshire");
  await expect(
    page.getByRole("heading", { name: "Berkshire Hathaway", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Recent Changes" }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/investor-${test.info().project.name}.png`,
    fullPage: true,
  });
  await page.locator('a[href="/research/AAPL"]').first().click();
  await expect(
    page.getByRole("heading", { name: "Ideas to Track" }),
  ).toBeVisible();
  await expect(page.getByTestId("suggested-thesis").first()).toBeVisible();
  const trackIdea = page
    .getByTestId("suggested-thesis")
    .filter({
      has: page.getByRole("button", { name: "Track idea", exact: true }),
    })
    .first()
    .getByRole("button", { name: "Track idea", exact: true });
  if (await trackIdea.count()) await trackIdea.click();
  await page
    .getByText("Advanced tracking, disclosures, and source details", {
      exact: true,
    })
    .click();
  await expect(page.getByTestId("tracked-thesis").first()).toBeVisible();
  const tracked = page.getByTestId("tracked-thesis").last();
  const trackedText = await tracked.getByRole("heading").first().innerText();
  await tracked.getByRole("button", { name: "Evaluate evidence" }).click();
  const evaluated = page
    .getByTestId("tracked-thesis")
    .filter({ hasText: trackedText });
  await expect(
    evaluated.getByRole("list", { name: "Thesis timeline" }),
  ).toBeVisible();
  await page.reload();
  await page
    .getByText("Advanced tracking, disclosures, and source details", {
      exact: true,
    })
    .click();
  await expect(
    page
      .getByTestId("tracked-thesis")
      .filter({ hasText: trackedText })
      .getByRole("list", { name: "Thesis timeline" }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/research-${test.info().project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
test("watchlist works without a thesis and Ask does not invent rationale", async ({
  page,
}) => {
  await page.goto("/research/NVDA");
  await expect(
    page.getByRole("heading", { name: "Ideas to Track" }),
  ).toBeVisible();
  const add = page.getByRole("button", {
    name: "Add to Watchlist",
    exact: true,
  });
  if (await add.count()) await add.click();
  await expect(
    page.getByRole("button", { name: "Watching", exact: true }),
  ).toBeVisible();
  const homeFeed = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/home/feed" && response.ok(),
  );
  await page.getByRole("link", { name: "Home", exact: true }).click();
  await homeFeed;
  await expect(
    page.getByRole("heading", { name: "My Watchlist" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "NVDA", exact: true }).last(),
  ).toBeVisible();
  await page.goto("/ask");
  await page
    .getByLabel("What would you like to investigate?")
    .fill("Why did Berkshire reduce AAPL?");
  await page
    .getByRole("button", { name: "Ask ThesisLens", exact: true })
    .click();
  await expect(
    page.getByText(/There is no sourced Berkshire Hathaway explanation/),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/ask-${test.info().project.name}.png`,
    fullPage: true,
  });
});
test("NVDA evidence and suggested thesis can be evaluated", async ({
  page,
}) => {
  await page.goto("/research/NVDA");
  await expect(page.getByTestId("suggested-thesis").first()).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "What’s New", exact: true }),
  ).toBeVisible();
  const trackIdea = page
    .getByTestId("suggested-thesis")
    .filter({
      has: page.getByRole("button", { name: "Track idea", exact: true }),
    })
    .first()
    .getByRole("button", { name: "Track idea", exact: true });
  if (await trackIdea.count()) await trackIdea.click();
  await page
    .getByText("Advanced tracking, disclosures, and source details", {
      exact: true,
    })
    .click();
  await expect(page.getByTestId("tracked-thesis").first()).toBeVisible();
  const tracked = page.getByTestId("tracked-thesis").last();
  const trackedText = await tracked.getByRole("heading").first().innerText();
  await tracked.getByRole("button", { name: "Evaluate evidence" }).click();
  await expect(
    page
      .getByTestId("tracked-thesis")
      .filter({ hasText: trackedText })
      .getByRole("list", { name: "Thesis timeline" }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/nvda-${test.info().project.name}.png`,
    fullPage: true,
  });
});
test("followed GOOGL disclosure answer stays factual and sourced", async ({
  page,
  request,
}) => {
  await request.put("/api/investors/berkshire/follow", {
    data: { enabled: true },
  });
  await page.goto("/ask");
  await page
    .getByLabel("What would you like to investigate?")
    .fill("Which investors I follow disclose GOOGL?");
  await page
    .getByRole("button", { name: "Ask ThesisLens", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "What the evidence supports" }),
  ).toBeVisible();
  const evidence = page.getByText(/Sources & evidence/);
  const sourceLinks = page.getByRole("link", { name: "Original source ↗" });
  if (await evidence.count()) {
    await evidence.click();
    await expect(sourceLinks.first()).toHaveAttribute("href", /sec.gov/);
  } else {
    await expect(page.getByText(/No verified matching holdings/)).toBeVisible();
  }
});
test("errors are usable and missing sources are not invented", async ({
  page,
}) => {
  await page.route("**/api/home/feed", (route) =>
    route.fulfill({ status: 503, body: "Unavailable" }),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Research is temporarily unavailable" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await page.unroute("**/api/home/feed");
  await page.goto("/research/ZZZZZZ");
  await expect(
    page.getByRole("heading", {
      name: "Research is still taking shape",
    }),
  ).toBeVisible();
});

test("portfolio and partial-data pages remain polished", async ({ page }) => {
  for (const [slug, heading] of [
    ["ark", "ARK Invest — ARKK"],
    ["berkshire", "Berkshire Hathaway"],
    ["pershing", "Pershing Square"],
  ]) {
    await page.goto(`/discover/${slug}`);
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: `test-results/${slug}-${test.info().project.name}.png`,
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  await page.goto("/research/RKLB");
  await expect(
    page.getByRole("heading", { name: /Rocket Lab|RKLB/i }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/rklb-${test.info().project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
