import { execFileSync } from "node:child_process";

/** Reload the deterministic fixture before every e2e run. */
export default function globalSetup() {
  execFileSync("uv", ["run", "python", "-m", "scripts.seed_e2e"], { cwd: "../backend", stdio: "inherit", shell: process.platform === "win32" });
}
