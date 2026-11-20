const path = require("node:path");
const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
    testDir: __dirname,
    outputDir: path.resolve(__dirname, "../../test-results"),
    use: {
        ...devices["Pixel 7"],
        browserName: "chromium",
        channel: process.env.PLAYWRIGHT_CHANNEL || "chromium",
        baseURL: "http://127.0.0.1:8717",
        launchOptions: { args: ["--use-fake-device-for-media-stream"] },
    },
    webServer: {
        command: `${process.platform === "win32" ? "python" : "python3"} -m http.server 8717 --bind 127.0.0.1 --directory web`,
        cwd: path.resolve(__dirname, "../.."),
        url: "http://127.0.0.1:8717",
        reuseExistingServer: false,
    },
});
