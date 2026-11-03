// File: tests/e2e/layout.spec.ts
import { test, expect } from "@playwright/test";

test("navigation and metadata align using the actual templates", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        await page.goto("/?query=voyage");
        await expect(page.locator(".result-row")).toHaveCount(6);
        const header = await page.evaluate(() => {
            const logo = document.querySelector(".masthead-logo-img")!.getBoundingClientRect();
            const menu = document.querySelector("#mobile-menu-btn")!.getBoundingClientRect();
            return { logoTop: logo.top, menuTop: menu.top, logoRight: logo.right, menuLeft: menu.left };
        });
        expect(Math.abs(header.logoTop - header.menuTop)).toBeLessThan(1);
        expect(header.logoRight).toBeLessThan(header.menuLeft);
        await page.locator("#mobile-menu-btn").click();
        await expect(page.locator("#theme-selector")).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(page.locator("#mobile-menu-btn")).toBeFocused();
        const switchBox = await page.locator(".view-toggle-container").boundingBox();
        await expect(page.locator("#view-list-btn svg")).toBeVisible();
        await expect(page.locator("#view-grid-btn svg")).toBeVisible();
        await page.locator("#view-list-btn").focus();
        await page.keyboard.press("Enter");
        await expect(page.locator("#view-list-btn")).toHaveAttribute("aria-pressed", "true");
        await expect(page.locator("#view-list-btn span")).toBeVisible();
        await expect(page.locator("#view-grid-btn span")).toBeHidden();
        for (const id of ["#view-list-btn", "#view-grid-btn"]) {
            const box = await page.locator(id).boundingBox();
            expect(Math.round(box!.width * 100) / 100).toBeGreaterThanOrEqual(44);
            expect(Math.round(box!.height * 100) / 100).toBeGreaterThanOrEqual(44);
        }
        expect((await page.locator(".view-toggle-container").boundingBox())!.width).toBe(switchBox!.width);
        await expect
            .poll(async () =>
                page
                    .locator(".action-buttons")
                    .first()
                    .evaluate((group) => {
                        const boxes = Array.from(group.children, (element) => element.getBoundingClientRect());
                        return (
                            boxes.every((box) => box.width >= 64 && box.height >= 44) &&
                            Math.abs(boxes[0].width - boxes[1].width) < 1
                        );
                    })
            )
            .toBe(true);
        const pair = await page
            .locator(".action-buttons")
            .first()
            .evaluate((group) =>
                Array.from(group.children, (element) => {
                    const rect = element.getBoundingClientRect();
                    return { width: rect.width, height: rect.height };
                })
            );
        expect(Math.abs(pair[0].width - pair[1].width)).toBeLessThan(1);
        expect(Math.abs(pair[0].height - pair[1].height)).toBeLessThan(1);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await page.locator("#view-grid-btn").click();
        await expect(page.locator("#view-grid-btn span")).toBeVisible();
        await expect(page.locator("#view-list-btn span")).toBeHidden();
        await expect(page.locator("#view-grid-btn")).toHaveAttribute("aria-pressed", "true");
        if (width > 420) {
            const rows = await page.locator(".result-row").evaluateAll((rows) =>
                rows.map((row) => ({
                    y: Math.round(row.getBoundingClientRect().y),
                    category: row.querySelector(".categories-container")!.getBoundingClientRect().y,
                }))
            );
            const sameRow = rows.filter((row) => row.y === rows[0].y);
            expect(
                Math.max(...sameRow.map((row) => row.category)) - Math.min(...sameRow.map((row) => row.category))
            ).toBeLessThan(1);
        }
    }
    expect(errors).toEqual([]);
});

test("history and search loading stay compact on mobile", async ({ page }) => {
    await page.addInitScript(() =>
        sessionStorage.setItem(
            "recentSearches",
            JSON.stringify(["voyage", "clock", "a long search phrase", "harbor", "map"])
        )
    );
    await page.setViewportSize({ width: 320, height: 1000 });
    await page.goto("/?query=voyage");
    await expect(page.locator(".search-panel .recent-search-list li")).toHaveCount(5);
    const clearHistory = page.getByRole("button", { name: "Clear recent searches", exact: true });
    await expect(clearHistory).toHaveText("");
    await expect(clearHistory).toHaveAttribute("title", "Clear recent searches");
    const clearBox = await clearHistory.boundingBox();
    expect(clearBox!.width).toBeGreaterThanOrEqual(44);
    expect(clearBox!.height).toBeGreaterThanOrEqual(44);
    const idle = await page.locator(".search-button").boundingBox();
    await page.evaluate(() => (window as any).showLoadingSpinner());
    await expect(page.locator(".search-button")).toHaveAttribute("aria-busy", "true");
    const busy = await page.locator(".search-button").boundingBox();
    expect(Math.abs(idle!.width - busy!.width)).toBeLessThan(1);
    await page.evaluate(() => (window as any).hideLoadingSpinner());
    await clearHistory.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#recent-searches")).toBeHidden();
    await expect(page.locator("#main-search-input")).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("a long query leaves room for clear text and clearing preserves results and filters", async ({ page }) => {
    for (const width of [1440, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        await page.goto("/?query=" + encodeURIComponent("author:" + "A very long contributor name ".repeat(12)));
        await page.locator("#toolbar-filter-toggle").click();
        await page.locator("#author-filter").selectOption("Mira Sol");
        await page.locator("#filter-button").click();
        await expect(page.locator(".search-input-wrapper")).toHaveClass(/has-overflow/);
        const input = page.locator("#main-search-input");
        const clear = page.getByRole("button", { name: "Clear search text" });
        await expect(clear).toBeVisible();
        const box = await clear.boundingBox();
        expect(Math.round(box!.width * 100) / 100).toBeGreaterThanOrEqual(44);
        expect(
            await clear.evaluate((element) => {
                const rect = element.getBoundingClientRect();
                return (
                    document
                        .elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
                        ?.closest("#clear-search-btn") === element
                );
            })
        ).toBe(true);
        expect(
            parseFloat(await input.evaluate((element) => getComputedStyle(element).paddingRight))
        ).toBeGreaterThanOrEqual(52);
        await input.focus();
        expect(await input.evaluate((element) => getComputedStyle(element).maskImage)).toBe("none");
        await input.evaluate((element) => element.blur());
        expect(await input.evaluate((element) => getComputedStyle(element).maskImage)).not.toBe("none");
        const url = page.url();
        await clear.click();
        await expect(input).toHaveValue("");
        await expect(input).toBeFocused();
        await expect(clear).toBeHidden();
        await expect(page).toHaveURL(url);
        await expect(page.locator(".result-row:visible")).toHaveCount(2);
        await expect(page.locator("#author-filter")).toHaveValue("Mira Sol");
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
});

test("list dates stay with book information, including newly loaded results", async ({ page }) => {
    await page.goto("/?query=voyage");
    await expect(page.locator(".col-actions .book-posted")).toHaveCount(6);
    await page.locator("#view-list-btn").click();
    await expect(page.locator(".col-info .book-posted")).toHaveCount(6);
    await expect(page.locator(".col-actions .book-posted")).toHaveCount(0);
    await page.evaluate(async () => {
        await (window as any).loadNextPage("voyage");
    });
    await expect(page.locator(".col-info .book-posted")).toHaveCount(7);
    await page.locator("#view-grid-btn").click();
    await expect(page.locator(".col-actions .book-posted")).toHaveCount(7);
    await expect(page.locator(".book-posted")).toHaveCount(7);
});

test("reset is in Filters and clears committed filters", async ({ page }) => {
    await page.goto("/?query=voyage");
    await expect(page.locator("#toolbar-clear-btn")).toHaveCount(0);
    await page.locator("#toolbar-filter-toggle").click();
    await page.locator("#author-filter").selectOption("Mira Sol");
    await page.locator("#filter-button").click();
    await expect(page.locator(".result-row:visible")).toHaveCount(2);
    await page.locator("#toolbar-filter-toggle").click();
    await page.getByRole("button", { name: "Reset filters", exact: true }).click();
    await page.keyboard.press("Escape");
    await expect(page.locator("#author-filter")).toHaveValue("");
    await expect(page.locator(".result-row:visible")).toHaveCount(6);
});
