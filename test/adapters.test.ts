import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile, mkdir, copyFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import test from "node:test";
import { generate } from "../tools/generate-adapters/index.js";

test("hand edits are detected by the same generate plus git diff check used in CI", async () => {
  const root = await mkdtemp(join(tmpdir(), "adapter-generation-"));
  await mkdir(join(root, "policy"));
  await copyFile(new URL("../policy/capabilities.yaml", import.meta.url), join(root, "policy/capabilities.yaml"));
  execFileSync("git", ["init", "-q"], { cwd: root });
  await generate(root);
  execFileSync("git", ["add", "AGENTS.md", "policy/capabilities.yaml"], { cwd: root });
  execFileSync("git", ["-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "baseline"], { cwd: root });

  await writeFile(join(root, "AGENTS.md"), `${await readFile(join(root, "AGENTS.md"), "utf8")}hand edit\n`);
  assert.throws(() => execFileSync("git", ["diff", "--exit-code"], { cwd: root, stdio: "pipe" }));
  await generate(root);
  execFileSync("git", ["diff", "--exit-code"], { cwd: root });
});
