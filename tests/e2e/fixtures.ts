// File: tests/e2e/fixtures.ts
import { test as base, expect } from "@playwright/test";

export const test = base.extend<{ appChecks: void }>({
    appChecks: [
        async ({ page, context, request }, use) => {
            await context.route(
                (url) => !["127.0.0.1", "localhost"].includes(url.hostname),
                (route) => route.abort()
            );
            const reset = await request.post("/e2e/client", { data: { reset: true } });
            expect(reset.ok()).toBe(true);
            const errors: string[] = [];
            page.on("pageerror", (error) => errors.push(error.message));
            await use();
            if (test.info().status !== test.info().expectedStatus) {
                const state = await (await request.get("/e2e/client")).json();
                await test.info().attach("isolated-client-state", {
                    body: JSON.stringify(state, null, 2),
                    contentType: "application/json",
                });
            }
            expect(errors, "Unexpected browser JavaScript errors").toEqual([]);
        },
        { auto: true },
    ],
});
export { expect };
