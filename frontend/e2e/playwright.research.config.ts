import base from "../playwright.config";
import { defineConfig } from "playwright/test";

/** Research visual tests on the installed Google Chrome (no bundled browser download needed). */
export default defineConfig({
  ...base,
  testDir: ".",
  testMatch: "research.spec.ts",
  use: { ...base.use, channel: "chrome", baseURL: process.env.PLAYWRIGHT_BASE_URL || base.use?.baseURL },
  webServer: process.env.PLAYWRIGHT_BASE_URL ? undefined : base.webServer,
});
