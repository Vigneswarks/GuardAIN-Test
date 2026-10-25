const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const session = {}, local = {}, messages = [], closed = [];
let listener, calls = 0;
let tab = {id: 7, windowId: 1, url: 'https://news.example/article'};
const storage = data => ({
  get: async key => typeof key === 'object' && key !== null ? {...key, ...data} : key ? {[key]: data[key]} : {...data},
  set: async entries => Object.assign(data, entries),
  remove: async key => { delete data[key]; }
});
const chrome = {
  storage: {local: storage(local), session: storage(session)},
  alarms: {create() {}, onAlarm: {addListener() {}}},
  tabs: {get: async () => tab, query: async () => [tab], update: async () => {},
    sendMessage: async (id, message) => messages.push(message), remove: async id => closed.push(id),
    onRemoved: {addListener() {}}},
  runtime: {onMessage: {addListener(fn) {listener = fn;}}, onInstalled: {addListener() {}}},
  webNavigation: {onCommitted: {addListener() {}}},
  action: {setBadgeText: async () => {}, setBadgeBackgroundColor: async () => {}},
  notifications: {create: async () => {}}
};
const context = vm.createContext({chrome, console, URL, AbortController, AbortSignal, setTimeout, clearTimeout,
  fetch: async () => { calls++; return {ok: true, json: async () => ({action: 'ALLOW', score: .1, reasons: []})}; }});
vm.runInContext(fs.readFileSync('extension/background.js', 'utf8'), context);
(async () => {
  const localHighRisk = context.offlineClassify({url_host: 'controlled.test', signals: {
    credential_form: true, coercion: true, urgent_demand: true, insecure_form: true
  }});
  assert.equal(localHighRisk.risk_level, 'high_risk', 'Offline policy requires corroborated structural facts');
  assert.equal(context.offlineClassify({url_host: 'controlled.test', signals: {coercion: true, urgent_demand: true}}).risk_level, 'unknown', 'Keywords alone must not block');
  await context.scanSignal({url_host: 'google.com', url: 'https://google.com'}, 7);
  assert.equal(calls, 0, 'Safe zones must never contact cloud');
  await context.scanSignal({url_host: 'news.example', url: tab.url, text_sample: 'digital arrest CBI urgent'}, 7);
  assert.equal(session['verdict:7'].risk_level, 'safe');
  assert.equal(messages.some(m => m.type === 'BLOCK_PAGE'), false);
  listener({type: 'AUTO_CLOSE_WARNING_TAB'}, {tab, frameId: 0});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(closed.length, 0, 'Unverified closure must fail');
  session['verdict:7'] = {risk_level: 'high_risk', host: 'news.example', documentUrl: tab.url, scannedAt: Date.now() - 9000};
  listener({type: 'AUTO_CLOSE_WARNING_TAB'}, {tab, frameId: 0});
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(closed, [7]);
  session['verdict:7'].documentUrl = 'https://news.example/old';
  listener({type: 'AUTO_CLOSE_WARNING_TAB'}, {tab, frameId: 0});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(closed.length, 1, 'Navigation must invalidate closure');
  console.log('Extension policy/closure regressions passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
