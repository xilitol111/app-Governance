#!/usr/bin/env node
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { parse } from "yaml";
import { normalizeLf } from "../../adapters/types.js";

type Rule = { id: string; reason: string; ci_check?: string };

export function renderAgents(source: string): string {
  const document = parse(normalizeLf(source)) as { rules: Rule[] };
  const rows = document.rules.map((rule) => {
    const check = rule.ci_check ? ` (ci_check: \`${rule.ci_check}\`)` : "";
    return `- **${rule.id}**: ${rule.reason}${check}`;
  });
  return normalizeLf(`# Generated from policy/capabilities.yaml. Do not edit by hand.\n\n${rows.join("\n")}\n`);
}

export async function generate(root = process.cwd()): Promise<string> {
  const source = await readFile(resolve(root, "policy/capabilities.yaml"), "utf8");
  const output = renderAgents(source);
  await writeFile(resolve(root, "AGENTS.md"), output, "utf8");
  return output;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname)) await generate();
