const { test, expect } = require("@playwright/test");

// Coordinates are measured on a 720 × 480 source image.
const outline = [[70, 45], [650, 45], [650, 435], [70, 435]];

async function importSheet(page, visibleEdge) {
    const encodedPng = await page.evaluate(edge => {
        const sheet = document.createElement("canvas");
        sheet.width = 720;
        sheet.height = 480;
        const ctx = sheet.getContext("2d");
        ctx.fillStyle = edge ? "#39474b" : "#fffefa";
        ctx.fillRect(0, 0, 720, 480);
        ctx.fillStyle = "#fffefa";
        ctx.fillRect(70, 45, 581, 391);
        ctx.fillStyle = "#224790";
        ctx.fillRect(110, 83, 22, 22);
        ctx.fillStyle = "#283543";
        ctx.font = "bold 25px sans-serif";
        ctx.fillText("Lembar kalibrasi", 150, 104);
        ctx.font = "16px sans-serif";
        ctx.fillText("SAMPEL CETAK   /   02", 110, 143);
        ctx.fillRect(110, 170, 500, 2);
        ctx.fillText("01     Penanda orientasi", 110, 218);
        ctx.fillText("02     Skala abu-abu", 110, 285);
        ["#39444b", "#69767b", "#98a3a8", "#c6cdce"].forEach((tone, i) => {
            ctx.fillStyle = tone;
            ctx.fillRect(160 + 76 * i, 310, 62, 23);
        });
        ctx.fillStyle = "#c25f4d";
        ctx.fillRect(536, 352, 42, 28);
        return sheet.toDataURL("image/png").split(",")[1];
    }, visibleEdge);
    const detected = page.waitForResponse(response => response.url().endsWith("/api/corners"));
    await page.locator("#photo-file").setInputFiles({
        name: "calibration.png", mimeType: "image/png", buffer: Buffer.from(encodedPng, "base64"),
    });
    return (await (await detected).json()).corners;
}

async function sourcePosition(page, [x, y]) {
    // Use the source canvas to derive a touch coordinate independently of the overlay.
    const source = page.locator("#page-preview");
    await source.scrollIntoViewIfNeeded();
    const box = await source.boundingBox();
    const scale = Math.min(box.width / 720, box.height / 480);
    return [
        box.x + (box.width - 720 * scale) / 2 + x * scale,
        box.y + (box.height - 480 * scale) / 2 + y * scale,
    ];
}

async function inspectResult(page) {
    const preview = page.locator("#corrected-preview");
    await expect(preview).toBeVisible();
    return preview.evaluate(async img => {
        await img.decode();
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);
        const pixel = (x, y) => [...ctx.getImageData(x, y, 1, 1).data].slice(0, 3);
        return { width: canvas.width, height: canvas.height, blue: pixel(51, 49), red: pixel(487, 320) };
    });
}

test("pick four corners by touch after failed detection and rectify at source resolution", async ({ page }) => {
    await page.goto("/");
    expect(await importSheet(page, false)).toBeNull();
    const apply = page.locator("#apply-corners");
    const overlay = page.locator("#corner-overlay");
    await expect(overlay).toBeVisible();
    await expect(apply).toBeDisabled();
    for (const corner of outline) {
        const [x, y] = await sourcePosition(page, corner);
        await page.touchscreen.tap(x, y);
    }
    await expect(overlay.locator(".corner-handle")).toHaveCount(4);
    await apply.click();
    const result = await inspectResult(page);
    expect(Math.abs(result.width - 581)).toBeLessThanOrEqual(5);
    expect(Math.abs(result.height - 391)).toBeLessThanOrEqual(5);
    expect(result.blue).toEqual([34, 71, 144]);
    expect(result.red).toEqual([194, 95, 77]);
});

test("adjust an automatically detected corner before applying the warp", async ({ page, context }) => {
    await page.goto("/");
    expect(await importSheet(page, true)).toHaveLength(4);
    const handles = page.locator("#corner-overlay .corner-handle");
    await expect(handles).toHaveCount(4);
    if (process.env.TRUESCAN_CORNERS_SCREENSHOT) {
        await page.screenshot({ path: process.env.TRUESCAN_CORNERS_SCREENSHOT, fullPage: true });
    }
    await handles.first().scrollIntoViewIfNeeded();
    const [x, y] = await sourcePosition(page, [30, 70]);
    const box = await handles.first().boundingBox();
    const session = await context.newCDPSession(page);
    const touch = (type, touchPoints) => session.send("Input.dispatchTouchEvent", { type, touchPoints });
    await touch("touchStart", [{ x: box.x + box.width / 2, y: box.y + box.height / 2 }]);
    await touch("touchMove", [{ x, y }]);
    await touch("touchEnd", []);
    const positions = nodes => nodes.map(node => [node.style.left, node.style.top]);
    const edited = await handles.evaluateAll(positions);
    await page.locator("#apply-corners").click();
    const result = await inspectResult(page);
    expect(Math.abs(result.width - 622)).toBeLessThanOrEqual(6);
    expect(Math.abs(result.height - 391)).toBeLessThanOrEqual(6);
    await page.locator("#edit-corners").click();
    await expect(page.locator("#corrected-preview")).toBeHidden();
    await expect(page.locator("#page-preview")).toBeVisible();
    await expect(handles).toHaveCount(4);
    expect(await handles.evaluateAll(positions)).toEqual(edited);
});
