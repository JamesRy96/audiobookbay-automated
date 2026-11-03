// File: tests/e2e/contracts.spec.ts
import { test, expect } from "./fixtures";

test("Details dispatch creates the correct task, and Remove cancellation preserves it", async ({ page, request }) => {
    await page.goto("/?query=voyage");
    await page.locator(".details-button").first().click();
    await expect(page.locator(".details-container h1")).toContainText("The Clockmaker's Voyage");
    await page.locator(".details-download-btn").click();
    await expect(page.locator(".toast")).toContainText("Sent to your Download Client");
    let state = await (await request.get("/e2e/client")).json();
    expect(state.events).toHaveLength(1);
    expect(state.events[0]).toMatchObject({
        action: "add",
        hash: "1".repeat(40),
        name: "The Clockmaker's Voyage - Mira Sol",
        category: "abb-automated",
        save_path: "/downloads/audiobooks/The Clockmaker's Voyage - Mira Sol",
    });
    expect(state.events[0].magnet).toContain("xt=urn:btih:" + "1".repeat(40));
    await page.goto("/status");
    await page.locator("#auto-refresh-toggle").uncheck();
    const remove = page.locator(`.remove-torrent-btn[data-torrent-id="${"1".repeat(40)}"]`);
    await expect(remove).toHaveCount(1);
    await remove.click();
    await page.locator("#modal-cancel").click();
    state = await (await request.get("/e2e/client")).json();
    expect(state.events).toHaveLength(1);
    expect(state.torrents.some((job: any) => job.hash === "1".repeat(40))).toBe(true);
    await remove.click();
    await page.locator("#modal-confirm").click();
    await expect(remove).toHaveCount(0);
    state = await (await request.get("/e2e/client")).json();
    expect(state.events.at(-1)).toEqual({ action: "remove", hash: "1".repeat(40), delete_files: false });
    expect(state.torrents.map((job: any) => job.hash)).toEqual(["fixture-1"]);
});

test("absolute catalog links dispatch the selected book rather than a fallback", async ({ page, request }) => {
    await page.goto("/?query=voyage");
    const second = page.locator(".result-row").nth(1);
    await expect(second.locator(".send-torrent-btn")).toHaveAttribute(
        "data-link",
        "https://catalog.example/abss/book-1/"
    );
    await second.locator(".send-torrent-btn").click();
    await expect(page.locator(".toast")).toContainText("Sent to your Download Client");
    const state = await (await request.get("/e2e/client")).json();
    expect(state.events).toHaveLength(1);
    expect(state.events[0]).toMatchObject({
        hash: "2".repeat(40),
        name: "A Long Journey: The Last Map, Book 2 - Owen Vale",
    });
});

test("client rejection restores Download and retry creates exactly one task", async ({ page, request }) => {
    await request.post("/e2e/client", { data: { fail_add: true } });
    await page.goto("/?query=voyage");
    const button = page.locator(".send-torrent-btn").first();
    const failed = page.waitForResponse((response) => response.url().endsWith("/send"));
    await button.click();
    expect((await failed).status()).toBe(500);
    await expect(page.locator(".toast")).toContainText("Could not start download");
    await expect(button).toBeEnabled();
    expect((await (await request.get("/e2e/client")).json()).events).toHaveLength(0);
    await request.post("/e2e/client", { data: { fail_add: false } });
    await button.click();
    await expect(page.locator(".toast").last()).toContainText("Sent to your Download Client");
    expect((await (await request.get("/e2e/client")).json()).events).toHaveLength(1);
});

test("missing hashes and unknown catalog paths never dispatch a fallback book", async ({ page, request }) => {
    await page.goto("/?query=missing-hash");
    const response = page.waitForResponse((response) => response.url().endsWith("/send"));
    await page.locator(".send-torrent-btn").click();
    expect((await response).status()).toBe(404);
    await expect(page.locator(".toast")).toContainText("Could not start download");
    await expect(page.locator(".send-torrent-btn").first()).toBeEnabled();
    await page.goto("/details?link=/abss/unknown-book/");
    await expect(page.locator(".details-download-btn")).toHaveCount(0);
    expect((await (await request.get("/e2e/client")).json()).events).toHaveLength(0);
});

test("empty catalog HTML produces an empty page without inventing records", async ({ page, request }) => {
    const response = await request.get("/api/search?query=empty");
    expect(response.status()).toBe(200);
    expect((await response.json()).books).toEqual([]);
    await page.goto("/?query=empty");
    await expect(page.locator(".result-row")).toHaveCount(0);
    await expect(page.locator("main")).toContainText("No audiobooks found");
});

test("manual pagination retains results after failure and retries the real next page", async ({ page }) => {
    await page.addInitScript(() => Reflect.deleteProperty(window, "IntersectionObserver"));
    let attempts = 0;
    await page.route("**/api/search?**", async (route) => {
        attempts++;
        if (attempts === 1) await route.fulfill({ status: 503, json: { error: "Isolated outage" } });
        else await route.continue();
    });
    await page.goto("/?query=voyage");
    await page.locator("#load-more-btn").click();
    await expect(page.locator("#load-more-btn")).toHaveText("Retry loading audiobooks");
    await expect(page.locator(".result-row")).toHaveCount(6);
    await page.locator("#load-more-btn").click();
    await expect(page.locator(".result-row")).toHaveCount(7);
    await expect(page.locator(".book-title").last()).toHaveText("The Winter Clock");
    await page.locator("#load-more-btn").click();
    await expect(page.locator("#load-more-end")).toBeVisible();
    expect(attempts).toBe(3);
});

test("external navigation requires confirmation and opens the actual book URL", async ({ page, context, request }) => {
    let externalRequests = 0;
    await context.route("https://catalog.example/**", async (route) => {
        externalRequests++;
        await route.fulfill({ contentType: "text/html", body: "<h1>Isolated external catalog</h1>" });
    });
    await page.goto("/details?link=/abss/book-0/");
    await page.locator(".direct-link-btn").click();
    await page.locator("#modal-cancel").click();
    expect(externalRequests).toBe(0);
    expect(context.pages()).toHaveLength(1);
    await page.locator(".direct-link-btn").click();
    const opened = context.waitForEvent("page");
    await page.locator("#modal-confirm").click();
    const external = await opened;
    await expect(external).toHaveURL("https://catalog.example/abss/book-0/");
    await expect(external.locator("h1")).toHaveText("Isolated external catalog");
    expect(externalRequests).toBe(1);
    expect((await (await request.get("/e2e/client")).json()).events).toHaveLength(0);
});

test("a late cookie-less background response cannot invalidate Download", async ({ page, request }) => {
    await page.goto("/?query=voyage");
    await page.route("**/api/search?query=a", async (route) => {
        const response = await route.fetch({ headers: { ...route.request().headers(), cookie: "" } });
        expect(response.headers()["set-cookie"]).toBeUndefined();
        await route.fulfill({ response });
    });
    await page.evaluate(() => fetch("/api/search?query=a").then((response) => response.json()));
    await page.locator(".send-torrent-btn").first().click();
    await expect(page.locator(".toast")).toContainText("Sent to your Download Client");
    expect((await (await request.get("/e2e/client")).json()).events).toHaveLength(1);
});
