import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import test from "node:test";
import { checkSecrets, findSecrets, inspectHookEvent } from "../tools/agent-guard/index.js";

test("detects credentials and redacts their values", () => {
  const credential = ["abcdefgh", "ijklmnop", "12345678"].join("");
  const findings = findSecrets(`api_key = '${credential}'`);
  assert.equal(findings.length, 1);
  assert.ok(!findings[0].match.includes(credential));
});

test("checks response and report text in hook events", () => {
  const credential = ["abcdefgh", "ijklmnop", "12345678"].join("");
  assert.equal(inspectHookEvent({ event: "agent_end", response: `access_token=${credential}` }).length, 1);
  assert.equal(inspectHookEvent({ event: "agent_end", report: "nothing sensitive" }).length, 0);
});

test("repository paths are resolved from an arbitrary absolute root", async () => {
  const root = await mkdtemp(join(tmpdir(), "guard-repository-"));
  execFileSync("git", ["init", "-q"], { cwd: root });
  const credential = ["abcdefgh", "ijklmnop", "12345678"].join("");
  await writeFile(join(root, "sample.txt"), `password=${credential}\n`);
  execFileSync("git", ["add", "sample.txt"], { cwd: root });
  const findings = await checkSecrets(resolve(root));
  assert.equal(findings.length, 1);
  assert.match(findings[0].label, /^sample\.txt:/);
});
