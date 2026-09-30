// Unit tests for the CloudFront Functions.
// Run: node --test infra/app/functions/functions.test.mjs
// The functions are plain scripts (CloudFront's runtime has no modules), so
// load each one and pull out its `handler`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function load(file) {
  const src = readFileSync(new URL(file, import.meta.url), "utf8");
  return new Function(`${src}\nreturn handler;`)();
}

const run = (handler, uri) => handler({ request: { uri, querystring: {} } }).uri;

test("web-rewrite maps directory URLs to index.html", () => {
  const handler = load("./web-rewrite.js");
  assert.equal(run(handler, "/"), "/index.html");
  assert.equal(run(handler, "/league/teams/"), "/league/teams/index.html");
  assert.equal(run(handler, "/league/teams"), "/league/teams/index.html");
  assert.equal(run(handler, "/_next/static/chunks/app.js"), "/_next/static/chunks/app.js");
  assert.equal(run(handler, "/icon.svg"), "/icon.svg");
  assert.equal(run(handler, "/404.html"), "/404.html");
});

test("api-strip-prefix removes the /api prefix", () => {
  const handler = load("./api-strip-prefix.js");
  assert.equal(run(handler, "/api/leagues"), "/leagues");
  assert.equal(run(handler, "/api/leagues/1/dashboard"), "/leagues/1/dashboard");
  assert.equal(run(handler, "/api/"), "/");
  assert.equal(run(handler, "/api"), "/");
});
