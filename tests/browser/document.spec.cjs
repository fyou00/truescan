const { execFileSync } = require("node:child_process");
const { existsSync, writeFileSync } = require("node:fs");
const path = require("node:path");
const { test, expect } = require("@playwright/test");

async function addSheet(page, portrait, total) {
    const data = await page.evaluate(vertical => {
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
        ctx.fillStyle = vertical ? "#c75037" : "#244ca0";
        const x = w * (vertical ? 0.25 : 0.75);
        const y = h * (vertical ? 0.4 : 0.7);
        ctx.fillRect(x - 18, y - 14, 36, 28);
        return photo.toDataURL("image/png").split(",")[1];
    }, portrait);
    const detected = page.waitForResponse(response => response.url().endsWith("/api/corners"));
    await page.locator("#photo-file").setInputFiles({
        name: portrait ? "calibration.png" : "color.png", mimeType: "image/png",
        buffer: Buffer.from(data, "base64"),
    });
    expect((await (await detected).json()).corners).toHaveLength(4);
    await expect(page.locator("#corner-message")).toContainText("Empat sudut ditemukan");
    await page.locator("#apply-corners").click();
    await expect(page.locator("#corrected-preview")).toBeVisible();
    await page.locator("#add-page").click();
    await expect(page.locator("#document-pages > li")).toHaveCount(total);
}

async function readPreview(image, portrait) {
    return image.evaluate(async (img, vertical) => {
        await img.decode();
        const bitmap = document.createElement("canvas");
        bitmap.width = img.naturalWidth;
        bitmap.height = img.naturalHeight;
        const ctx = bitmap.getContext("2d");
        ctx.drawImage(img, 0, 0);
        const x = bitmap.width * (vertical ? 0.25 : 0.75);
        const y = bitmap.height * (vertical ? 0.4 : 0.7);
        return {
            portrait: bitmap.height > bitmap.width,
            marker: [...ctx.getImageData(x, y, 1, 1).data].slice(0, 3),
            png: bitmap.toDataURL("image/png").split(",")[1],
        };
    }, portrait);
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
    const previewPaths = [landscape, portrait].map(({ png }, i) => {
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
        path.join(__dirname, "verify_document.py"), pdf, ...previewPaths,
    ]);
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
