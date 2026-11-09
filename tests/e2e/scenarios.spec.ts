// File: tests/e2e/scenarios.spec.ts
import { test, expect } from "./fixtures";

test("search, narrow loaded results, inspect details and send to the isolated client", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("textbox", { name: "Search audiobooks by title, author, or keyword" }).fill("voyage");
    await page.locator(".search-button").click();
    await expect(page.locator(".book-title").first()).toContainText("The Clockmaker's Voyage");
    await page.locator("#toolbar-filter-toggle").click();
    await expect(page.locator("#filter-scope-note")).toHaveText("Filters apply to results loaded so far.");
    await page.locator("#author-filter").selectOption("Mira Sol");
    await page.locator("#filter-button").click();
    await expect(page.locator(".result-row:visible")).toHaveCount(2);
    await page.locator(".result-row:visible .details-button").first().click();
    await expect(page.locator(".details-container h1")).toContainText("The Clockmaker's Voyage");
    await expect(page.locator(".details-description")).not.toContainText("Written by");
    await expect(page.locator(".details-description")).toContainText("lost clocks");
    await expect(
        page
            .locator(".meta-item")
            .filter({ has: page.locator(".meta-label", { hasText: "Narrator" }) })
            .locator("a")
    ).toHaveCount(2);
    const narrator = page.locator(".meta-item").filter({ has: page.locator(".meta-label", { hasText: "Narrator" }) });
    await expect(narrator.getByText("full cast", { exact: true })).toBeVisible();
    await expect(narrator.locator("a", { hasText: "full cast" })).toHaveCount(0);
    await page.locator(".details-download-btn").click();
    await expect(page.locator(".toast")).toContainText("Sent to your Download Client");
});

test("pagination has one end state and preserves the selected filter", async ({ page }) => {
    await page.goto("/?query=voyage");
    await page.locator("#toolbar-filter-toggle").click();
    await page.locator("#author-filter").selectOption("Mira Sol");
    await page.locator("#filter-button").click();
    await page.evaluate(async () => {
        await (window as any).streamRemainingPages("voyage", 2, 3);
    });
    await expect(page.locator("#author-filter")).toHaveValue("Mira Sol");
    await expect(page.locator("#load-more-end")).toBeVisible();
    await expect(page.locator("#load-more-end")).toHaveText("End of results");
    await expect(page.locator("#results-summary")).toHaveCount(0);
    await expect(page.locator(".result-row")).toHaveCount(7);
});

test("short queries explain the correction without echoing character counts", async ({ page }) => {
    await page.goto("/");
    const input = page.locator("#main-search-input");
    await input.fill("a");
    await page.locator(".search-button").click();
    expect(await input.evaluate((element: HTMLInputElement) => element.validationMessage)).toBe(
        "Enter at least 2 characters."
    );
    await input.fill("ab");
    expect(await input.evaluate((element: HTMLInputElement) => element.validationMessage)).toBe("");
});

test("status and diagnostics expose usable live controls", async ({ page }) => {
    for (const url of ["/status", "/diagnostics"]) {
        await page.goto(url);
        await expect(page.locator("main")).toBeVisible();
        await page.locator("#auto-refresh-toggle").uncheck();
        await expect(page.locator(".auto-refresh-text")).toHaveText("Paused");
        await page.locator("#auto-refresh-toggle").check();
        await expect(page.locator(".auto-refresh-text")).toHaveText("Live");
    }
});

test("an expired page explains how to recover without sending a download", async ({ page, request }) => {
    await page.goto("/?query=voyage");
    await page
        .locator('meta[name="csrf-token"]')
        .evaluate((element) => element.setAttribute("content", "expired-token"));
    const download = page.locator(".send-torrent-btn").first();
    await download.click();
    await expect(page.locator(".toast")).toContainText("Page expired. Refresh and try again.");
    await expect(download).toBeEnabled();
    expect((await (await request.get("/e2e/client")).json()).events).toHaveLength(0);
    await page.reload();
    await page.locator(".send-torrent-btn").first().click();
    await expect(page.locator(".toast")).toContainText("Sent to your Download Client");
});

test("a slow next page has a single loading row and no duplicate loading button", async ({ page }) => {
    let release!: () => void;
    let requests = 0;
    const waiting = new Promise<void>((resolve) => {
        release = resolve;
    });
    await page.route("**/api/search?**", async (route) => {
        requests++;
        await waiting;
        await route.fulfill({ json: { books: [], has_more: false, page: 2 } });
    });
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/?query=voyage");
    await page.locator("#load-more-indicator").scrollIntoViewIfNeeded();
    await expect(page.locator("#load-more-indicator")).toHaveAttribute("aria-busy", "true");
    await expect(page.locator("#pagination-message")).toHaveText("Loading audiobooks…");
    await expect(page.locator("#load-more-loading")).toBeVisible();
    await expect(page.locator("#load-more-btn")).toBeHidden();
    const geometry = await page.locator("#pagination-message").evaluate((element) => {
        const spinner = element.querySelector("#load-more-loading")!.getBoundingClientRect();
        const text = element.querySelector("#pagination-text")!.getBoundingClientRect();
        return Math.abs(spinner.top + spinner.height / 2 - (text.top + text.height / 2));
    });
    expect(geometry).toBeLessThan(1);
    await page.evaluate(() => {
        void (window as any).loadNextPage("voyage");
    });
    expect(requests).toBe(1);
    release();
    await expect(page.locator("#load-more-end")).toHaveText("End of results");
    await expect(page.locator("#load-more-end")).toBeVisible();
    await expect(page.locator("#pagination-message")).toBeHidden();
    await expect(page.locator("#load-more-loading")).toBeHidden();
    await expect(page.locator("#load-more-btn")).toBeHidden();
});

for (const mode of ["grid", "list"]) {
    test(`Download accepts relative links from initial and appended ${mode} results`, async ({ page, request }) => {
        await page.goto("/?query=voyage");
        await page.locator(`#view-${mode}-btn`).click();
        const first = page.locator(".send-torrent-btn").first();
        const initialLink = await first.getAttribute("data-link");
        expect(initialLink).toMatch(/^\/abss\//);
        const initialResponse = page.waitForResponse(
            (response) => response.url().endsWith("/send") && response.request().method() === "POST"
        );
        await first.click();
        const initial = await initialResponse;
        expect(initial.status()).toBe(200);
        expect(initial.request().postDataJSON().link).toBe(initialLink);
        let state = await (await request.get("/e2e/client")).json();
        expect(state.events).toHaveLength(1);
        expect(state.events[0]).toMatchObject({
            action: "add",
            hash: "1".repeat(40),
            name: "The Clockmaker's Voyage - Mira Sol",
            category: "abb-automated",
            save_path: "/downloads/audiobooks/The Clockmaker's Voyage - Mira Sol",
        });
        await expect(page.locator(".toast").last()).toContainText("Sent to your Download Client");
        await page.locator("#load-more-indicator").scrollIntoViewIfNeeded();
        await expect(page.locator(".result-row")).toHaveCount(7);
        const appended = page.locator(".send-torrent-btn").last();
        expect(await appended.getAttribute("data-link")).toMatch(/^\/abss\//);
        const appendedResponse = page.waitForResponse(
            (response) => response.url().endsWith("/send") && response.request().method() === "POST"
        );
        await appended.click();
        expect((await appendedResponse).status()).toBe(200);
        state = await (await request.get("/e2e/client")).json();
        expect(state.events).toHaveLength(2);
        expect(state.events[1]).toMatchObject({
            action: "add",
            hash: "7".repeat(40),
            name: "The Winter Clock - Ada Moon",
        });
        expect(state.torrents.some((job: any) => job.hash === "7".repeat(40))).toBe(true);
    });
}
