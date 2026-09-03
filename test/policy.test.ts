import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { parse } from "yaml";

const EVENTS = new Set([
  "before_tool",
  "after_tool",
  "session_start",
  "session_end",
  "pre_compact",
  "agent_end",
  "agent_start",
]);
const CORE_EVENTS = new Set([
  "before_tool",
  "after_tool",
  "session_start",
  "session_end",
  "pre_compact",
]);
const TOOL_CLASSES = new Set(["shell", "file_write", "network"]);
const ENFORCEMENTS = new Set(["required", "provider_extension"]);
const REQUIRED_FIELDS = [
  "id",
  "scope",
  "event",
  "match",
  "action",
  "enforcement",
  "reason",
] as const;

type Rule = Record<string, unknown> & {
  event: string;
  match: { tool_class: string };
  enforcement: string;
};

test("capability rules conform to the minimum policy schema", async () => {
  const source = await readFile(new URL("../policy/capabilities.yaml", import.meta.url), "utf8");
  const document = parse(source) as { rules?: Rule[] };

  assert.ok(Array.isArray(document.rules), "rules must be an array");
  assert.equal(document.rules.length, 5, "the initial five common rules must exist");

  for (const rule of document.rules) {
    for (const field of REQUIRED_FIELDS) {
      assert.ok(rule[field] !== undefined && rule[field] !== "", `${String(rule.id)} requires ${field}`);
    }
    assert.ok(EVENTS.has(rule.event), `${String(rule.id)} uses an unknown event`);
    assert.ok(rule.match && TOOL_CLASSES.has(rule.match.tool_class), `${String(rule.id)} uses an unknown tool class`);
    assert.ok(ENFORCEMENTS.has(rule.enforcement), `${String(rule.id)} uses an unknown enforcement`);

    if (rule.enforcement === "required") {
      assert.ok(CORE_EVENTS.has(rule.event), `${String(rule.id)} must use a core event`);
      assert.equal(typeof rule.ci_check, "string", `${String(rule.id)} requires ci_check`);
      assert.ok((rule.ci_check as string).trim().length > 0, `${String(rule.id)} requires a non-empty ci_check`);
    }
  }
});
