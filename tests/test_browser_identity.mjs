import { readFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../pydanticConvoAgent/components/visitor_identity/index.html', import.meta.url), 'utf8');
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
function browser({ cookie = '', blocked = false, throws = false } = {}) {
  const messages = [], writes = [];
  let render;
  const parent = { postMessage: message => messages.push(message) };
  const window = { parent, location: { origin: 'https://cyberbud.test', protocol: 'https:' }, addEventListener: (_, callback) => { render = callback; } };
  const document = {};
  Object.defineProperty(document, 'cookie', {
    get() { if (throws) throw Error('Cookies blocked'); return cookie; },
    set(value) { writes.push(value); if (!blocked) cookie = value.split(';')[0]; },
  });
  runInNewContext(script, { window, document, crypto: webcrypto, Uint8Array });
  return {
    messages, writes,
    render(event = {}) { render({ source: parent, origin: window.location.origin, data: { type: 'streamlit:render' }, ...event }); },
    cookie: () => cookie,
    values: () => messages.filter(m => m.type === 'streamlit:setComponentValue').map(m => m.value),
  };
}

test('new browsers receive distinct private tokens and secure persistent cookies', () => {
  const a = browser(), b = browser(); a.render(); b.render();
  assert.match(a.values()[0], /^[a-f0-9]{64}$/);
  assert.notEqual(a.values()[0], b.values()[0]);
  assert.match(a.writes[0], /Max-Age=31536000; SameSite=Lax; Secure$/);
});
test('rerenders and a returning browser keep the same token without rerun loops', () => {
  const a = browser(); a.render(); a.render();
  assert.equal(a.values().length, 1);
  const returning = browser({ cookie: a.cookie() }); returning.render();
  assert.equal(returning.values()[0], a.values()[0]);
  assert.equal(returning.writes.length, 0);
});
test('a malformed token is replaced rather than used as an identity', () => {
  const a = browser({ cookie: 'cyberbud_visitor=../shared-database' }); a.render();
  assert.match(a.values()[0], /^[a-f0-9]{64}$/);
});
test('blocked or throwing cookie access returns an error and never an identity', () => {
  for (const options of [{ blocked: true }, { throws: true }]) {
    const a = browser(options); a.render();
    assert.equal(a.values()[0].error, 'cookies_unavailable');
  }
});
test('messages from other windows or origins cannot trigger identity disclosure', () => {
  const a = browser();
  a.render({ origin: 'https://attacker.test' });
  a.render({ source: {} });
  assert.equal(a.values().length, 0);
  assert.equal(a.writes.length, 0);
});
