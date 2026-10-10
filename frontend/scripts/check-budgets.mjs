// Fails the build if any route's first-load JavaScript exceeds the budget (run after `npm run build`).
// First load = the app entry plus the route's chunk and everything they import statically. Lazy imports
// (the three.js scene, the MapLibre/deck.gl globe) load afterwards and are reported, not budgeted.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const BUDGET_KB = 250;
const manifest = JSON.parse(readFileSync("dist/.vite/manifest.json", "utf8"));
const gz = (file) => gzipSync(readFileSync(`dist/${file}`)).length / 1024;

function closure(key, seen = new Set()) {
  const chunk = manifest[key];
  if (!chunk || seen.has(chunk.file)) return seen;
  seen.add(chunk.file);
  for (const dep of chunk.imports ?? []) closure(dep, seen);
  return seen;
}

const entryKey = Object.keys(manifest).find((k) => manifest[k].isEntry);
const entry = closure(entryKey);
let failed = false;
console.log(`first-load JS per route (gzip, budget ${BUDGET_KB} KB):`);
for (const [key, chunk] of Object.entries(manifest)) {
  if (!chunk.isDynamicEntry || !/Page\.tsx$/.test(key)) continue;
  const files = closure(key, new Set(entry));
  const kb = [...files].filter((f) => f.endsWith(".js")).reduce((sum, f) => sum + gz(f), 0);
  const over = kb > BUDGET_KB;
  failed ||= over;
  console.log(`  ${over ? "FAIL" : "ok  "} ${key.split("/").at(-1).padEnd(18)} ${kb.toFixed(1).padStart(7)} KB`);
}
console.log("lazy chunks (loaded after first paint):");
for (const [key, chunk] of Object.entries(manifest)) {
  if (chunk.isDynamicEntry && !/Page\.tsx$/.test(key) && chunk.file.endsWith(".js")) {
    console.log(`       ${key.split("/").at(-1).padEnd(18)} ${gz(chunk.file).toFixed(1).padStart(7)} KB`);
  }
}
process.exit(failed ? 1 : 0);
