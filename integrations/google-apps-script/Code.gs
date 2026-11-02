/**
 * Google Form -> lead webhook bridge.
 *
 * Sends every new Google Form response to the lead webhook as JSON. The same script works
 * with BOTH backends in this repository:
 *   - the Python/FastAPI service  (POST https://your-host/webhooks/leads)
 *   - the n8n workflow            (POST https://your-n8n/webhook/real-estate-lead)
 *
 * Setup (details in docs/GOOGLE_FORM_SETUP.md):
 *   1. Form -> Responses -> Link to Sheets -> open the sheet -> Extensions -> Apps Script.
 *   2. Paste this file. Project Settings -> Script properties, add:
 *        WEBHOOK_URL     the full webhook URL
 *        WEBHOOK_SECRET  the same value as the server's WEBHOOK_SECRET
 *   3. Run setupTrigger() once and approve the permissions.
 *   4. Run testSubmission() to send a sample lead without touching the form.
 *
 * The secret lives in Script Properties, never in the code, so it is not exposed when the
 * script or sheet is shared.
 */

// Map the question titles in YOUR form to the webhook fields. Matching ignores case and
// surrounding spaces. Add your own wording to a list if the form uses different titles.
var FIELD_TITLES = {
  fullName: ['full name', 'name', 'your name'],
  email: ['email', 'email address', 'your email'],
  phone: ['phone', 'phone number', 'mobile', 'mobile number', 'whatsapp number', 'contact number'],
  propertyType: ['property type', 'type of property'],
  budget: ['budget', 'your budget', 'budget (pkr)'],
  preferredLocation: ['preferred location', 'location', 'area', 'preferred area'],
  buyingTimeline: ['buying timeline', 'timeline', 'when do you plan to buy', 'purchase timeline'],
  message: ['message', 'additional details', 'comments', 'notes']
};

/** Trigger entry point: runs on every form submission. */
function onFormSubmit(e) {
  var payload = buildPayload(e.namedValues || {}, new Date());
  var result = sendLead(payload);
  if (!result.ok) {
    // Throwing makes the failure visible in Apps Script's Executions and emails the script owner
    // (Triggers -> failure notifications).
    throw new Error('Lead webhook failed: HTTP ' + result.status + ' ' + result.body);
  }
}

/** Pure function: form answers -> webhook JSON. Exported to the Node test via module.exports below. */
function buildPayload(namedValues, now) {
  var lookup = {};
  Object.keys(namedValues).forEach(function (title) {
    var values = namedValues[title];
    lookup[String(title).trim().toLowerCase()] = Array.isArray(values) ? String(values[0] || '').trim() : String(values || '').trim();
  });

  var payload = { submittedAt: (now || new Date()).toISOString() };
  Object.keys(FIELD_TITLES).forEach(function (field) {
    var titles = FIELD_TITLES[field];
    for (var i = 0; i < titles.length; i++) {
      if (lookup[titles[i]]) {
        payload[field] = lookup[titles[i]];
        break;
      }
    }
  });
  payload.source = 'Google Form';
  return payload;
}

function sendLead(payload) {
  var props = PropertiesService.getScriptProperties();
  var url = props.getProperty('WEBHOOK_URL');
  var secret = props.getProperty('WEBHOOK_SECRET');
  if (!url) throw new Error('Script property WEBHOOK_URL is not set.');
  if (!secret) throw new Error('Script property WEBHOOK_SECRET is not set.');

  // The secret goes in the header (Python service) and in the body (n8n workflow reads body.secret).
  var body = JSON.stringify(Object.assign({}, payload, { secret: secret }));
  var response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-Webhook-Secret': secret },
    payload: body,
    muteHttpExceptions: true
  });
  var status = response.getResponseCode();
  return { ok: status >= 200 && status < 300, status: status, body: response.getContentText().slice(0, 300) };
}

/** Run once from the editor to install the "on form submit" trigger. */
function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'onFormSubmit') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('onFormSubmit').forSpreadsheet(SpreadsheetApp.getActive()).onFormSubmit().create();
  Logger.log('Trigger installed. New form responses will be sent to the webhook.');
}

/** Run from the editor to check the connection with a clearly labelled sample lead. */
function testSubmission() {
  var payload = buildPayload({
    'Full Name': ['Test Lead (delete me)'], 'Email': ['test.lead@example.com'], 'Phone': ['0300 1234567'],
    'Property Type': ['Residential plot'], 'Budget': ['PKR 1.5 crore'], 'Preferred Location': ['Islamabad'],
    'Buying Timeline': ['within 30 days'], 'Message': ['Connection test from Apps Script']
  }, new Date());
  var result = sendLead(payload);
  Logger.log('HTTP ' + result.status + ' ' + result.body);
}

if (typeof module !== 'undefined') module.exports = { buildPayload: buildPayload, FIELD_TITLES: FIELD_TITLES };
