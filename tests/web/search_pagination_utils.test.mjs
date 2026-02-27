import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const {
  resolvePageSize,
  computeTotalPages,
  clampPage,
  shouldRefetchForClampedPage,
} = require("../../web/js/search_pagination_utils.js");

test("resolvePageSize falls back for invalid values", () => {
  assert.equal(resolvePageSize(undefined, 60), 60);
  assert.equal(resolvePageSize("0", 60), 60);
  assert.equal(resolvePageSize("-2", 60), 60);
  assert.equal(resolvePageSize("15", 60), 15);
});

test("computeTotalPages handles empty and multi-page totals", () => {
  assert.equal(computeTotalPages(0, 60), 1);
  assert.equal(computeTotalPages(1, 60), 1);
  assert.equal(computeTotalPages(61, 60), 2);
  assert.equal(computeTotalPages(120, 60), 2);
});

test("clampPage enforces [1, totalPages] bounds", () => {
  assert.equal(clampPage(0, 5), 1);
  assert.equal(clampPage(3, 5), 3);
  assert.equal(clampPage(9, 5), 5);
});

test("shouldRefetchForClampedPage only when total>0 and page changed", () => {
  assert.equal(shouldRefetchForClampedPage(9, 1, 10), true);
  assert.equal(shouldRefetchForClampedPage(1, 1, 10), false);
  assert.equal(shouldRefetchForClampedPage(9, 1, 0), false);
});
