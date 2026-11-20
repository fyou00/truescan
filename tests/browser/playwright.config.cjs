const path = require("node:path");
const { existsSync } = require("node:fs");
const { defineConfig, devices } = require("@playwright/test");

const root = path.resolve(__dirname, "../..");
const windows = process.platform === "win32";
const venv = path.join(root, ".venv", windows ? "Scripts/python.exe" : "bin/python");
const python = existsSync(venv) ? venv : (windows ? "python" : "python3");

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
        command: `"${python}" -m truescan.server --port 8717`,
        cwd: root,
        url: "http://127.0.0.1:8717",
        reuseExistingServer: false,
    },
});
