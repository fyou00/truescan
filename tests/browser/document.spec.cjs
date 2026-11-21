const { execFileSync } = require("node:child_process");
const { existsSync, writeFileSync } = require("node:fs");
const path = require("node:path");
const { test, expect } = require("@playwright/test");

async function addSheet(page, portrait, total, markerColor = portrait ? "#c75037" : "#244ca0") {
    const data = await page.evaluate(({ vertical, markerColor }) => {
        const photo = document.createElement("canvas");
        const w = vertical ? 320 : 520;
        const h = vertical ? 460 : 300;
        photo.width = w + 80;
        photo.height = h + 80;
        const ctx = photo.getContext("2d");
        ctx.fillStyle = "#31444c";
        ctx.fillRect(0, 0, photo.width, photo.height);
        ctx.translate(40, 40);
        ctx.fillStyle = "#faf9f4";
        ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = "#203547";
        ctx.font = "bold 24px sans-serif";
        ctx.fillText(vertical ? "Lembar kalibrasi" : "Catatan warna", 20, 44);
        ctx.font = "13px sans-serif";
        ctx.fillText(vertical ? "DOKUMEN SINTETIS  /  01" : "DOKUMEN SINTETIS  /  02", 20, 68);
        ctx.fillRect(20, 82, w - 40, 2);
        ctx.font = "16px sans-serif";
        ctx.fillText("Sampel cetak", 20, 113);
        ctx.fillStyle = markerColor;
        const x = w * (vertical ? 0.25 : 0.75);
        const y = h * (vertical ? 0.4 : 0.7);
        ctx.fillRect(x - 18, y - 14, 36, 28);
        return photo.toDataURL("image/png").split(",")[1];
    }, { vertical: portrait, markerColor });
    const detected = page.waitForResponse(response => response.url().endsWith("/api/corners"));
    await page.locator("#photo-file").setInputFiles({
        name: portrait ? "calibration.png" : "color.png", mimeType: "image/png",
        buffer: Buffer.from(data, "base64"),
    });
    expect((await (await detected).json()).corners).toHaveLength(4);
    await expect(page.locator("#corner-message")).toContainText("Empat sudut ditemukan");
    await page.locator("#apply-corners").click();
    await expect(page.locator("#corrected-preview")).toBeVisible();
    const size = await page.locator("#corrected-preview").evaluate(img => [img.naturalWidth, img.naturalHeight]);
    await page.locator("#add-page").click();
    await expect(page.locator("#document-pages > li")).toHaveCount(total);
    return size;
}

async function readPreview(image, portrait, clockwiseTurns = 0) {
    return image.evaluate(async (img, { vertical, turns }) => {
        await img.decode();
        const bitmap = document.createElement("canvas");
        bitmap.width = img.naturalWidth;
        bitmap.height = img.naturalHeight;
        const ctx = bitmap.getContext("2d");
        ctx.drawImage(img, 0, 0);
        let [x, y] = vertical ? [0.25, 0.4] : [0.75, 0.7];
        for (let i = 0; i < turns; i++) [x, y] = [1 - y, x];
        return {
            portrait: bitmap.height > bitmap.width,
            marker: [...ctx.getImageData(x * bitmap.width, y * bitmap.height, 1, 1).data].slice(0, 3),
            png: bitmap.toDataURL("image/png").split(",")[1],
        };
    }, { vertical: portrait, turns: clockwiseTurns });
}

async function downloadAndCompare(page, testInfo, previews, mode, dimensions = []) {
    const previewPaths = previews.map(({ png }, i) => {
        const file = testInfo.outputPath(`preview-${i + 1}.png`);
        writeFileSync(file, Buffer.from(png, "base64"));
        return file;
    });
    const pending = page.waitForEvent("download");
    await page.locator("#download-pdf").click();
    const download = await pending;
    const pdf = testInfo.outputPath("document.pdf");
    await download.saveAs(pdf);
    expect(download.suggestedFilename()).toMatch(/\.pdf$/i);

    const windows = process.platform === "win32";
    const python = path.resolve(__dirname, "../..", ".venv", windows ? "Scripts/python.exe" : "bin/python");
    execFileSync(existsSync(python) ? python : (windows ? "python" : "python3"), [
        path.join(__dirname, "verify_document.py"), pdf, mode, JSON.stringify(dimensions), ...previewPaths,
    ]);
}

test("reorder two corrected pages and download a PDF matching the grayscale previews", async ({ page }, testInfo) => {
    test.setTimeout(60_000);
    await page.goto("/");
    await addSheet(page, true, 1);
    await addSheet(page, false, 2);
    await expect(page.locator("#download-pdf")).toBeEnabled();
    const images = page.locator("#document-pages > li img");
    await expect(images.first()).toBeVisible();
    await expect(images.last()).toBeVisible();
    let portrait = await readPreview(images.first(), true);
    let landscape = await readPreview(images.last(), false);
    expect(portrait.portrait).toBe(true);
    expect(landscape.portrait).toBe(false);
    expect(portrait.marker[0] - portrait.marker[2]).toBeGreaterThan(45);
    expect(landscape.marker[2] - landscape.marker[0]).toBeGreaterThan(45);

    await page.locator("#document-pages > li").last().locator(".move-up").click();
    await expect.poll(async () => (await readPreview(images.first(), false)).portrait).toBe(false);
    if (process.env.TRUESCAN_DOCUMENT_SCREENSHOT) {
        await page.screenshot({ path: process.env.TRUESCAN_DOCUMENT_SCREENSHOT, fullPage: true });
    }
    await page.locator("#document-mode").selectOption("grayscale");
    await expect(page.locator("#download-pdf")).toBeEnabled();
    await expect.poll(async () => {
        landscape = await readPreview(images.first(), false);
        portrait = await readPreview(images.last(), true);
        return [landscape, portrait].every(({ marker }) => Math.max(...marker) === Math.min(...marker));
    }).toBe(true);
    expect(landscape.portrait).toBe(false);
    expect(portrait.portrait).toBe(true);
    await downloadAndCompare(page, testInfo, [landscape, portrait], "grayscale");
});

test("retry a failed preview without losing the added page", async ({ page }) => {
    await page.route("**/api/preview", route => route.fulfill({
        status: 503, contentType: "application/json", body: JSON.stringify({ error: "Pratinjau gagal." }),
    }), { times: 1 });
    await page.goto("/");
    await addSheet(page, true, 1);
    const retry = page.locator("#retry-previews");
    const download = page.locator("#download-pdf");
    await expect(retry).toBeVisible();
    await expect(download).toBeDisabled();
    await retry.click();
    await expect(download).toBeEnabled();
    await expect(retry).toBeHidden();
    await expect(page.locator("#document-pages > li")).toHaveCount(1);
    const preview = await readPreview(page.locator("#document-pages img"), true);
    expect(preview.portrait).toBe(true);
    expect(preview.marker[0] - preview.marker[2]).toBeGreaterThan(45);
});

test("rotate only the second marked page in the preview and downloaded PDF", async ({ page }, testInfo) => {
    test.setTimeout(60_000);
    await page.goto("/");
    const firstSize = await addSheet(page, true, 1);
    const [secondWidth, secondHeight] = await addSheet(page, false, 2);
    const ready = page.locator("#download-pdf");
    await expect(ready).toBeEnabled();
    const images = page.locator("#document-pages > li img");
    const originalFirst = await readPreview(images.first(), true);
    const originalSecond = await readPreview(images.last(), false);
    for (let turns = 1; turns <= 4; turns++) {
        await page.locator("#document-pages > li").last().locator(".rotate-page").click();
        await expect(ready).toBeEnabled();
        const first = await readPreview(images.first(), true);
        const second = await readPreview(images.last(), false, turns);
        expect(first.png === originalFirst.png).toBe(true);
        expect(second.portrait).toBe(turns % 2 === 1);
        // Enhancement and thumbnail resampling run again in the new orientation.
        for (const [channel, value] of second.marker.entries()) {
            expect(Math.abs(value - originalSecond.marker[channel])).toBeLessThanOrEqual(3);
        }
        if (turns === 1) {
            if (process.env.TRUESCAN_ROTATION_SCREENSHOT) {
                await page.locator("#document-panel").scrollIntoViewIfNeeded();
                await page.screenshot({ path: process.env.TRUESCAN_ROTATION_SCREENSHOT });
            }
            await downloadAndCompare(page, testInfo, [first, second], "color",
                                     [firstSize, [secondHeight, secondWidth]]);
        }
        if (turns === 4) expect(second.png === originalSecond.png).toBe(true);
    }
});

test("remove the middle sheet, export the remaining pages and reuse the empty document", async ({ page }, testInfo) => {
    test.setTimeout(60_000);
    await page.goto("/");
    const firstSize = await addSheet(page, true, 1);
    await addSheet(page, false, 2);
    const thirdSize = await addSheet(page, true, 3, "#22824c");
    const rows = page.locator("#document-pages > li");
    const download = page.locator("#download-pdf");
    await expect(download).toBeEnabled();
    const first = await readPreview(rows.first().locator("img"), true);
    const middle = await readPreview(rows.nth(1).locator("img"), false);
    const third = await readPreview(rows.last().locator("img"), true);
    expect(first.marker[0] - first.marker[1]).toBeGreaterThan(45);
    expect(middle.marker[2] - middle.marker[0]).toBeGreaterThan(45);
    expect(third.marker[1] - third.marker[0]).toBeGreaterThan(45);

    await rows.nth(1).locator(".remove-page").click();
    await expect(rows).toHaveCount(2);
    await expect(rows.locator(".page-label")).toHaveText(["Halaman 1", "Halaman 2"]);
    const remainingFirst = await readPreview(rows.first().locator("img"), true);
    const remainingSecond = await readPreview(rows.last().locator("img"), true);
    expect(remainingFirst.png === first.png).toBe(true);
    expect(remainingSecond.png === third.png).toBe(true);
    if (process.env.TRUESCAN_REMOVAL_SCREENSHOT) {
        await page.locator("#document-panel").scrollIntoViewIfNeeded();
        await page.screenshot({ path: process.env.TRUESCAN_REMOVAL_SCREENSHOT });
    }
    await downloadAndCompare(page, testInfo, [first, third], "color", [firstSize, thirdSize]);

    await rows.first().locator(".remove-page").click();
    await rows.first().locator(".remove-page").click();
    await expect(rows).toHaveCount(0);
    await expect(download).toBeDisabled();
    await page.locator("#add-page").click();
    await expect(rows).toHaveCount(1);
    await expect(download).toBeEnabled();
    const restored = await readPreview(rows.first().locator("img"), true);
    expect(restored.png === third.png).toBe(true);
});
