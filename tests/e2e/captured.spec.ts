// File: tests/e2e/captured.spec.ts
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test, expect } from "./fixtures";

const capture = JSON.parse(readFileSync(join(__dirname, "catalog/captured/manifest.json"), "utf8"));

for (const mode of ["grid", "list"]) {
    test(`captured catalog search reaches the correct downloader task in ${mode}`, async ({ page, request }) => {
        await page.goto("/?query=recorded-hobbit");
        await page.locator(`#view-${mode}-btn`).click();
        await expect(page.locator(".result-row")).toHaveCount(capture.search.unique_paths.length);
        const button = page.locator(".send-torrent-btn").first();
        const link = await button.getAttribute("data-link");
        const book = capture.details.find(
            (book: any) => book.path === new URL(link!, "https://audiobookbay.lu").pathname
        );
        expect(book).toBeDefined();
        const response = page.waitForResponse((response) => response.url().endsWith("/send"));
        await button.click();
        expect((await response).status()).toBe(200);
        const state = await (await request.get("/e2e/client")).json();
        expect(state.events).toHaveLength(1);
        expect(state.events[0]).toMatchObject({ action: "add", hash: book.hash, name: book.title });
        expect(state.events[0].magnet.split("&tr=").length - 1).toBeGreaterThanOrEqual(book.trackers_in_text.length);
    });
}

for (const book of capture.details) {
    test(`captured Details preserves hash and tracker list: ${book.title}`, async ({ page, request }) => {
        await page.goto("/details?" + new URLSearchParams({ link: book.path }));
        await expect(page.locator(".details-container h1")).toHaveText(book.title);
        await expect(page.locator(".details-description")).not.toBeEmpty();
        await expect(page.locator(".details-description script")).toHaveCount(0);
        await page.locator(".technical-details summary").click();
        await expect(page.locator(".info-hash-value")).toHaveText(book.hash);
        await expect(page.locator(".tracker-item")).toHaveCount(book.trackers_in_text.length);
        await page.locator(".details-download-btn").click();
        await expect(page.locator(".toast")).toContainText("Sent to your Download Client");
        const state = await (await request.get("/e2e/client")).json();
        expect(state.events).toHaveLength(1);
        expect(state.events[0]).toMatchObject({ hash: book.hash, name: book.title });
        for (const tracker of book.trackers_in_text) expect(state.events[0].magnet).toContain(tracker);
    });
}

test("all visible native-mirror posts survive encoded catalog markup", async ({ page, request }) => {
    const response = await request.get("/api/search?query=recorded-encoded");
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.books.map((book: any) => book.link)).toEqual(
        capture.encoded_search.books.map((book: any) => book.link)
    );
    await page.goto("/?query=recorded-encoded");
    await expect(page.locator(".result-row")).toHaveCount(9);
});
