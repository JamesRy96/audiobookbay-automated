// File: tests/e2e/capture_screenshots.js
const { chromium } = require("@playwright/test");
const path = require("node:path");

(async () => {
    const base = process.env.SCREENSHOT_BASE_URL || "http://127.0.0.1:5078";
    const query = process.env.SCREENSHOT_QUERY || "dune";
    const browser = await chromium.launch({
        channel: process.env.PLAYWRIGHT_CHROMIUM_CHANNEL,
        proxy: process.env.SCREENSHOT_PROXY
            ? { server: process.env.SCREENSHOT_PROXY, bypass: "localhost,127.0.0.1" }
            : undefined,
    });
    try {
        const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, reducedMotion: "reduce" });
        page.setDefaultTimeout(60000);
        const errors = [];
        page.on("pageerror", (error) => errors.push(error.message));
        let referenceTheme;
        let details = process.env.SCREENSHOT_DETAILS_LINK;
        for (const name of ["search", "details", "status"]) {
            const url =
                name === "search" ? "/?query=" + encodeURIComponent(query) : name === "details" ? details : "/status";
            if (!url) throw new Error("No Details link found in search results.");
            const response = await page.goto(new URL(url, base).href, { timeout: 180000 });
            if (!response.ok()) throw new Error("Screenshot page failed: " + url);
            const selector =
                name === "search" ? ".result-row" : name === "details" ? ".details-container" : "#status-table-body";
            await page.locator(selector).first().waitFor({ state: "visible" });
            if (name === "status") {
                await page.waitForFunction(() => {
                    const body = document.querySelector("#status-table-body");
                    return body && !/^loading\b/i.test(body.innerText.trim()) && body.children.length > 0;
                });
            }
            await page.locator("img").evaluateAll(async (images) => {
                await Promise.all(
                    images
                        .filter((image) => image.loading !== "lazy" || image.getBoundingClientRect().top < innerHeight)
                        .map((image) => image.decode().catch(() => {}))
                );
            });
            if (name === "details") await page.locator("img.details-cover").evaluate((image) => image.decode());
            if (name === "search") {
                const rows = page.locator(".result-row");
                const top = (await rows.first().boundingBox()).y;
                for (const row of await rows.all()) {
                    if (Math.abs((await row.boundingBox()).y - top) > 2) break;
                    const cover = row.locator("img");
                    if (!(await cover.count())) throw new Error("A first-row result has no cover.");
                    await cover.evaluate((image) => image.decode());
                }
                details ||= await rows.first().locator('a[href^="/details?"]').first().getAttribute("href");
            }
            const theme = await page.evaluate(() => ({
                name: document.documentElement.getAttribute("data-theme"),
                background: getComputedStyle(document.body).backgroundImage,
                attachment: getComputedStyle(document.body).backgroundAttachment,
            }));
            if (name === "search") referenceTheme = theme;
            else if (JSON.stringify(theme) !== JSON.stringify(referenceTheme))
                throw new Error("Page theme differs: " + name);
            await page.screenshot({
                path: path.resolve(__dirname, "../../docs/images/" + name + ".png"),
                fullPage: false,
            });
        }
        if (errors.length) throw new Error(errors.join("\n"));
        process.stdout.write(
            "Updated screenshots from " + base + " using query " + query + ". Review before committing.\n"
        );
    } finally {
        await browser.close();
    }
})().catch((error) => {
    process.stderr.write(error.stack + "\n");
    process.exit(1);
});
