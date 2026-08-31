import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const inputs = process.argv.slice(2);
if (inputs.length === 0) {
  throw new Error("Usage: node render-dot.mjs <file.dot> [...]");
}

async function loadViz() {
  const candidates = [
    process.env.VIZ_JS_MODULE,
    "@viz-js/viz",
    "C:/Users/19850/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@viz-js/viz/dist/viz.js",
  ].filter(Boolean);
  const failures = [];
  for (const candidate of candidates) {
    try {
      const specifier = /^[A-Za-z]:\//.test(candidate) ? pathToFileURL(candidate).href : candidate;
      return await import(specifier);
    } catch (error) {
      failures.push(`${candidate}: ${error.message}`);
    }
  }
  throw new Error(`Unable to load @viz-js/viz.\n${failures.join("\n")}`);
}

const { instance } = await loadViz();
const viz = await instance();
for (const input of inputs) {
  const dot = await fs.readFile(input, "utf8");
  const svg = viz.renderString(dot, { format: "svg", engine: "dot" });
  const output = path.format({ ...path.parse(input), base: undefined, ext: ".svg" });
  await fs.writeFile(output, svg, "utf8");
  process.stdout.write(`${output}\n`);
}
