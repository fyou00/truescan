const path = require("node:path");
const { test, expect } = require("@playwright/test");

test("denied camera falls back to importing an EXIF-rotated page", async ({ page, context }) => {
    const session = await context.newCDPSession(page);
    await session.send("Browser.setPermission", {
        permission: { name: "camera" },
        setting: "denied",
        origin: "http://127.0.0.1:8717",
        browserContextId: (await session.send("Target.getTargetInfo")).targetInfo.browserContextId,
    });
    await page.goto("/");
    await page.locator("#open-camera").click();
    await expect(page.locator("#status")).toContainText(/izin kamera ditolak/i);
    const chooseFile = page.waitForEvent("filechooser");
    await page.locator("#import-photo").click();
    await (await chooseFile).setFiles(path.join(__dirname, "fixtures", "rotated-page.jpg"));
    const preview = page.locator("#page-preview");
    await expect(preview).toBeVisible();
    // JPEG storage is landscape. EXIF 6 restores portrait and the blue top-left mark.
    const result = await preview.evaluate(canvas => ({
        dimensions: [canvas.width, canvas.height],
        marker: [...canvas.getContext("2d").getImageData(44, 40, 1, 1).data],
    }));
    expect(result.dimensions).toEqual([480, 640]);
    for (const [index, channel] of [34, 71, 144].entries()) {
        expect(Math.abs(result.marker[index] - channel)).toBeLessThanOrEqual(6);
    }
    if (process.env.TRUESCAN_SCREENSHOT) {
        await page.screenshot({ path: process.env.TRUESCAN_SCREENSHOT, fullPage: true });
    }
});

test("capture a simulated camera frame and release the camera on capture and close", async ({
    context, page,
}) => {
    await context.grantPermissions(["camera"]);
    await page.goto("/");
    const video = page.locator("#camera-preview");
    for (const action of ["take-photo", "stop-camera"]) {
        await page.locator("#open-camera").click();
        await expect(page.locator("#take-photo")).toBeEnabled();
        await expect(video).toBeVisible();
        const track = await video.evaluateHandle(element => element.srcObject.getVideoTracks()[0]);
        const dimensions = await video.evaluate(element => [element.videoWidth, element.videoHeight]);
        expect(dimensions.every(value => value > 0)).toBe(true);
        await page.locator("#" + action).click();
        await expect(video).toBeHidden();
        await expect.poll(() => track.evaluate(value => value.readyState)).toBe("ended");
        await track.dispose();
        const preview = page.locator("#page-preview");
        await expect(preview).toBeVisible();
        expect(await preview.evaluate(canvas => [canvas.width, canvas.height])).toEqual(dimensions);
    }
});
