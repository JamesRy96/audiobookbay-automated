// File: tests/e2e/capture_screenshots.js
const { chromium } = require("@playwright/test");
const path = require("node:path");

(async () => {
    const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHROMIUM_CHANNEL });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, reducedMotion: "reduce" });
    const pages = [
        ["search", "/?query=voyage", ".result-row"],
        ["details", "/details?link=https%3A%2F%2Fcatalog.example%2Fbook-0", ".details-container"],
        ["status", "/status", "#status-table-body"],
    ];
    for (const [name, url, selector] of pages) {
        await page.setViewportSize({ width: 1440, height: name === "search" ? 1300 : 1100 });
        const response = await page.goto("http://127.0.0.1:5090" + url);
        if (!response.ok()) throw new Error("Fixture page failed: " + url);
        await page.locator(selector).first().waitFor({ state: "visible" });
        await page.locator("img").evaluateAll(async (images) => {
            await Promise.all(images.map((image) => image.decode().catch(() => {})));
        });
        const content = await page
            .locator(
                name === "search" ? ".result-row" : name === "details" ? ".details-container" : "#status-table-body"
            )
            .first()
            .boundingBox();
        if (!content) throw new Error("Screenshot content is missing: " + name);
        const clip = {
            x: 0,
            y: 0,
            width: 1440,
            height: Math.ceil(content.y + content.height + (name === "search" ? 8 : 40)),
        };
        await page.screenshot({ path: path.resolve(__dirname, "../../docs/images/" + name + ".png"), clip });
    }
    await browser.close();
    process.stdout.write("Updated default-theme screenshots using the isolated fixture.\n");
})().catch((error) => {
    process.stderr.write(error.stack + "\n");
    process.exit(1);
});
