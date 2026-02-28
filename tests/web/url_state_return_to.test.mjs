import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { buildReturnTo, parseSafeReturnTo, appendReturnTo } = require("../../web/js/url_state_utils.js");

test("buildReturnTo accepts site-relative paths and rejects external URLs", () => {
  assert.equal(buildReturnTo("/search?q=abc&page=2"), "/search?q=abc&page=2");
  assert.equal(buildReturnTo("https://evil.com/phish"), "/search");
  assert.equal(buildReturnTo("//evil.com/path"), "/search");
});

test("parseSafeReturnTo uses fallback when missing or unsafe", () => {
  assert.equal(parseSafeReturnTo("", "/search?q=1"), "/search?q=1");
  assert.equal(parseSafeReturnTo("?return_to=http://evil.com", "/search?q=1"), "/search?q=1");
  assert.equal(parseSafeReturnTo("?return_to=//evil.com", "/search?q=1"), "/search?q=1");
});

test("appendReturnTo writes only safe values", () => {
  const params = new URLSearchParams("q=abc");
  appendReturnTo(params, "/search?q=abc&page=3");
  assert.equal(params.get("return_to"), "/search?q=abc&page=3");

  const unsafe = new URLSearchParams("q=abc");
  appendReturnTo(unsafe, "http://evil.com");
  assert.equal(unsafe.has("return_to"), false);
});

test("round trip preserves search context from search to part and back", () => {
  const sourceSearch = "/search?q=00&match=all&page=2";
  const params = new URLSearchParams("q=00&match=all&page=2");
  appendReturnTo(params, buildReturnTo(sourceSearch));
  const partUrl = `/part/4?${params.toString()}`;
  const resolvedBack = parseSafeReturnTo(partUrl.split("?")[1], "/search");
  assert.equal(resolvedBack, sourceSearch);
});
