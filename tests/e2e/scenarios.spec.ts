// File: tests/e2e/scenarios.spec.ts
import { test, expect } from "@playwright/test";

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

test("an expired page explains how to recover without sending a download", async ({ page }) => {
    await page.goto("/?query=voyage");
    await page
        .locator('meta[name="csrf-token"]')
        .evaluate((element) => element.setAttribute("content", "expired-token"));
    const download = page.locator(".send-torrent-btn").first();
    await download.click();
    await expect(page.locator(".toast")).toContainText("Page expired. Refresh and try again.");
    await expect(download).toBeEnabled();
    await page.reload();
    await page.locator(".send-torrent-btn").first().click();
    await expect(page.locator(".toast")).toContainText("Sent to your Download Client");
});
