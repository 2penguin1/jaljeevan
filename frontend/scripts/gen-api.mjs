// Generate src/lib/api/schema.d.ts from the backend OpenAPI document (run from frontend/).
// Uses the committed backend/openapi.json (refresh: `cd backend && uv run python -m scripts.export_openapi`),
// so no running server is needed.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";

const spec = "../backend/openapi.json"; // relative: the repo path contains spaces
if (!existsSync(spec)) {
  console.error("backend/openapi.json missing: run `cd backend && uv run python -m scripts.export_openapi`");
  process.exit(1);
}
execFileSync("npx", ["openapi-typescript", spec, "-o", "src/lib/api/schema.d.ts"], {
  stdio: "inherit",
  shell: process.platform === "win32",
});
