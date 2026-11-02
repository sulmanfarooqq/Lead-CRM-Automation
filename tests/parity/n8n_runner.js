#!/usr/bin/env node
/*
 * Runs the REAL JavaScript from the n8n workflow's Code nodes ("Normalize & Validate"
 * and "Classify Lead") against a list of test payloads, so the Python implementation
 * can be compared with the workflow on identical inputs.
 *
 * Usage: node n8n_runner.js <workflow.json> <cases.json>
 * Output: JSON array on stdout, one entry per case.
 *
 * Only the n8n helpers the two nodes use are stubbed: $('Node').first().json, $input,
 * and $now (Luxon-style setZone/plus/toFormat). No network, no credentials.
 */
const fs = require("fs");

const [workflowPath, casesPath] = process.argv.slice(2);
if (!workflowPath || !casesPath) {
  console.error("usage: n8n_runner.js <workflow.json> <cases.json>");
  process.exit(2);
}

const workflow = JSON.parse(fs.readFileSync(workflowPath, "utf8"));
const cases = JSON.parse(fs.readFileSync(casesPath, "utf8"));
const node = (name) => {
  const found = workflow.nodes.find((n) => n.name === name);
  if (!found) throw new Error("node not found in workflow: " + name);
  return found;
};

// Config node -> plain object, exactly as the Set node would emit it.
const config = {};
for (const a of node("Config").parameters.assignments.assignments) config[a.name] = a.value;
config.webhookSecret = "parity-secret";

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const compile = (name) =>
  new AsyncFunction("$", "$input", "$now", "$execution", node(name).parameters.jsCode);

// Minimal Luxon-like clock: enough for $now.setZone(tz).plus({days}).toFormat('yyyy-MM-dd').
const fakeNow = {
  setZone() {
    return {
      plus({ days = 0 }) {
        const d = new Date(Date.now() + days * 86400000);
        return { toFormat: () => d.toISOString().slice(0, 10) };
      },
    };
  },
};

const outputs = {};
const dollar = (name) => ({ first: () => ({ json: outputs[name] }) });

(async () => {
  const normalize = compile("Normalize & Validate");
  const classify = compile("Classify Lead");
  const results = [];
  for (const c of cases) {
    outputs["Config"] = config;
    const body = { ...c.payload, secret: "parity-secret" };
    const n = (await normalize(dollar, { first: () => ({ json: { body } }) }, fakeNow, { id: "1" }))[0].json;
    const entry = { name: c.name, normalize: n, classify: null };
    if (!n.isRejected) {
      const k = (await classify(dollar, { first: () => ({ json: n }) }, fakeNow, { id: "1" }))[0].json;
      entry.classify = {
        priority: k.priority,
        followUpAction: k.followUpAction,
        reviewReasons: k.reviewReasons,
        timelineDays: k.timelineDays,
      };
    }
    results.push(entry);
  }
  process.stdout.write(JSON.stringify(results));
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
