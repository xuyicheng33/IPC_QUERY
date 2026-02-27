import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { detectKeywordFlags, highlightKeywords } = require("../../web/keyword_utils.js");

test("detectKeywordFlags matches optional and replace case-insensitively", () => {
  const flags = detectKeywordFlags("Optional part can REPLACE another unit.");
  assert.equal(flags.optional, true);
  assert.equal(flags.replace, true);
});

test("detectKeywordFlags does not treat replaced/replacement as replace hit", () => {
  const flags = detectKeywordFlags("replaced parts in replacement plan");
  assert.equal(flags.optional, false);
  assert.equal(flags.replace, false);
});

test("highlightKeywords highlights only whole-word hits", () => {
  const highlighted = highlightKeywords("OPTIONAL can replace; replaced should stay plain.");
  assert.match(highlighted, /<span class="kwHit">OPTIONAL<\/span>/);
  assert.match(highlighted, /<span class="kwHit">replace<\/span>/);
  assert.doesNotMatch(highlighted, /<span class="kwHit">replaced<\/span>/);
});

test("highlightKeywords escapes html before highlight and handles nullish", () => {
  const highlighted = highlightKeywords("<b>optional</b> & replace");
  assert.match(highlighted, /&lt;b&gt;<span class="kwHit">optional<\/span>&lt;\/b&gt;/);
  assert.match(highlighted, /&amp; <span class="kwHit">replace<\/span>/);
  assert.equal(highlightKeywords(null), "");
  assert.equal(highlightKeywords(undefined), "");
});
