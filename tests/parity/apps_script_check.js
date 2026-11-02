// Exercises integrations/google-apps-script/Code.gs: field mapping, header + body secret, error handling.
const assert = require("assert");
const path = require("path");
const sent = [];
global.PropertiesService = { getScriptProperties: () => ({ getProperty: (k) => ({ WEBHOOK_URL: "https://host/webhooks/leads", WEBHOOK_SECRET: "s3cr3t" }[k]) }) };
let nextStatus = 200;
global.UrlFetchApp = { fetch: (url, opts) => { sent.push({ url, opts }); return { getResponseCode: () => nextStatus, getContentText: () => "ok" }; } };
const gs = require(path.join(__dirname, "../../integrations/google-apps-script/Code.gs"));
Object.assign(global, require("vm").runInNewContext("0") ? {} : {});

// The .gs functions are globals in Apps Script; load them into this context for onFormSubmit.
const src = require("fs").readFileSync(path.join(__dirname, "../../integrations/google-apps-script/Code.gs"), "utf8");
new Function("module", "PropertiesService", "UrlFetchApp", src + "\nglobalThis.__gs = { onFormSubmit, sendLead };")(undefined, PropertiesService, UrlFetchApp);

const p = gs.buildPayload({
  "Full Name": ["  Sara Ali "], "Email Address": ["sara@example.com"], "Mobile Number": ["0311 1234567"],
  "Property Type": ["House"], "Budget (PKR)": ["50 lakh"], "Area": ["DHA"], "When do you plan to buy": ["within 2 weeks"],
  "Additional details": ["Hello"], "Unrelated question": ["ignored"],
}, new Date("2026-11-01T10:00:00Z"));
assert.deepStrictEqual(p, {
  submittedAt: "2026-11-01T10:00:00.000Z", fullName: "Sara Ali", email: "sara@example.com", phone: "0311 1234567",
  propertyType: "House", budget: "50 lakh", preferredLocation: "DHA", buyingTimeline: "within 2 weeks",
  message: "Hello", source: "Google Form",
});
assert.deepStrictEqual(gs.buildPayload({ "Full Name": [""] }, new Date(0)).fullName, undefined); // blank answers are omitted

globalThis.__gs.onFormSubmit({ namedValues: { "Full Name": ["A"], "Email": ["a@b.co"] } });
const call = sent[0];
assert.strictEqual(call.url, "https://host/webhooks/leads");
assert.strictEqual(call.opts.headers["X-Webhook-Secret"], "s3cr3t");
assert.strictEqual(JSON.parse(call.opts.payload).secret, "s3cr3t");
nextStatus = 401;
assert.throws(() => globalThis.__gs.onFormSubmit({ namedValues: { Email: ["a@b.co"] } }), /HTTP 401/);
console.log("apps script checks passed");
