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

async function simulateCameras(page, count) {
    await page.addInitScript(cameraCount => {
        const devices = [
            { deviceId: "rear", facingMode: "environment", label: "Rear camera" },
            { deviceId: "front", facingMode: "user", label: "Front camera" },
        ].slice(0, cameraCount);
        const tracks = [];
        navigator.mediaDevices.enumerateDevices = async () => devices.map(({ deviceId, label }) => ({
            kind: "videoinput", deviceId, label, groupId: "simulated",
        }));
        navigator.mediaDevices.getUserMedia = async ({ video }) => {
            const deviceId = video.deviceId?.exact;
            const facing = video.facingMode?.exact || video.facingMode?.ideal;
            const camera = deviceId ? devices.find(d => d.deviceId === deviceId) :
                devices.find(d => d.facingMode === facing) || devices[0];
            if (!camera) throw new DOMException("Camera unavailable", "OverconstrainedError");
            // Mobile hardware may require releasing the old camera before another can open.
            if (tracks.some(track => track.readyState === "live")) {
                throw new DOMException("Previous camera still active", "NotReadableError");
            }
            const frame = document.createElement("canvas");
            frame.width = 480;
            frame.height = 360;
            const stream = frame.captureStream(15);
            const track = stream.getVideoTracks()[0];
            const settings = track.getSettings.bind(track);
            track.getSettings = () => ({ ...settings(), deviceId: camera.deviceId, facingMode: camera.facingMode });
            tracks.push(track);
            const ctx = frame.getContext("2d");
            function drawFrame() {
                if (track.readyState !== "live") return;
                ctx.fillStyle = "#415653";
                ctx.fillRect(0, 0, 480, 360);
                ctx.fillStyle = "#fffdf7";
                ctx.fillRect(48, 27, 384, 306);
                ctx.fillStyle = camera.deviceId === "rear" ? "#b85241" : "#244f9d";
                ctx.fillRect(75, 55, 32, 32);
                ctx.font = "bold 21px sans-serif";
                ctx.fillText("Lembar kalibrasi", 125, 79);
                ctx.fillStyle = "#293d42";
                ctx.font = "15px sans-serif";
                ctx.fillText("SAMPEL KAMERA  /  " + (camera.deviceId === "rear" ? "01" : "02"), 75, 120);
                ctx.fillRect(75, 138, 324, 2);
                ctx.fillText("Penanda warna", 75, 180);
                ["#36464c", "#6b777c", "#a7afad", "#d9ddd8"].forEach((shade, i) => {
                    ctx.fillStyle = shade;
                    ctx.fillRect(75 + 80 * i, 200, 66, 28);
                });
                setTimeout(drawFrame, 80);
            }
            drawFrame();
            return stream;
        };
    }, count);
}

test("switch from the rear camera to the front camera and capture its marked frame", async ({ page }) => {
    await simulateCameras(page, 2);
    await page.goto("/");
    const video = page.locator("#camera-preview");
    const switchCamera = page.locator("#switch-camera");
    await page.locator("#open-camera").click();
    await expect(switchCamera).toBeVisible();
    const rear = await video.evaluateHandle(el => el.srcObject.getVideoTracks()[0]);
    expect(await rear.evaluate(track => track.getSettings().deviceId)).toBe("rear");
    await switchCamera.click();
    await expect.poll(() => video.evaluate(el => el.srcObject?.getVideoTracks()[0]?.getSettings().deviceId)).toBe("front");
    await expect(switchCamera).toBeVisible();
    await expect(page.locator("#take-photo")).toBeEnabled();
    expect(await rear.evaluate(track => track.readyState)).toBe("ended");
    const front = await video.evaluateHandle(el => el.srcObject.getVideoTracks()[0]);
    if (process.env.TRUESCAN_CAMERA_SWITCH_SCREENSHOT) {
        await page.screenshot({ path: process.env.TRUESCAN_CAMERA_SWITCH_SCREENSHOT });
    }
    await page.locator("#take-photo").click();
    const preview = page.locator("#page-preview");
    await expect(preview).toBeVisible();
    const pixel = await preview.evaluate(canvas => [...canvas.getContext("2d").getImageData(90, 70, 1, 1).data]);
    expect(pixel[2] - pixel[0]).toBeGreaterThan(60);
    expect(await front.evaluate(track => track.readyState)).toBe("ended");
    await rear.dispose();
    await front.dispose();
});

test("hide camera switching on a single-camera device and allow capture", async ({ page }) => {
    await simulateCameras(page, 1);
    await page.goto("/");
    await page.locator("#open-camera").click();
    await expect(page.locator("#take-photo")).toBeVisible();
    await expect(page.locator("#switch-camera")).toBeHidden();
    await page.locator("#take-photo").click();
    await expect(page.locator("#page-preview")).toBeVisible();
});
