#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { normalizeLf } from "../../adapters/types.js";

export type SecretFinding = { label: string; line: number; match: string };

const SECRET_PATTERNS: ReadonlyArray<[string, RegExp]> = [
  ["private key", /-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----/g],
  ["AWS access key", /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/g],
  ["GitHub token", /\b(?:gh[pousr]_[A-Za-z0-9_]{30,255}|github_pat_[A-Za-z0-9_]{40,255})\b/g],
  ["OpenAI/Stripe-style key", /\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}|\bsk-[A-Za-z0-9_-]{20,}\b/g],
  ["Google API key", /\bAIza[A-Za-z0-9_-]{35}\b/g],
  ["Slack token", /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g],
  ["bearer token", /\bBearer\s+[A-Za-z0-9_+\/.=-]{20,}\b/gi],
  ["JWT", /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g],
  ["generic credential", /\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password)\b\s*[:=]\s*["']?([A-Za-z0-9_+\/.=-]{16,})["']?/gi],
];

export function findSecrets(text: string): SecretFinding[] {
  const normalized = normalizeLf(text);
  const findings: SecretFinding[] = [];
  for (const [label, expression] of SECRET_PATTERNS) {
    expression.lastIndex = 0;
    for (const match of normalized.matchAll(expression)) {
      const matched = match[0];
      // Examples and placeholders are useful documentation, not credentials.
      if (/example|placeholder|your[_-]|dummy|redacted|<[^>]+>/i.test(matched)) continue;
      findings.push({ label, line: normalized.slice(0, match.index).split("\n").length, match: redact(matched) });
    }
  }
  return findings;
}

function redact(value: string): string {
  return value.length < 9 ? "[REDACTED]" : `${value.slice(0, 4)}…${value.slice(-4)}`;
}

export function inspectHookEvent(event: unknown): SecretFinding[] {
  const candidates: string[] = [];
  const visited = new Set<object>();
  // Walk the complete payload. This covers tool metadata and provider-specific
  // response/report fields (including nested message and output objects).
  const collect = (value: unknown): void => {
    if (typeof value === "string") { candidates.push(value); return; }
    if (!value || typeof value !== "object" || visited.has(value)) return;
    visited.add(value);
    for (const child of Object.values(value)) collect(child);
  };
  collect(event);
  return candidates.flatMap(findSecrets);
}

function repositoryFiles(root: string): string[] {
  const git = (args: string[]) => execFileSync("git", args, { cwd: root, encoding: "utf8" });
  const staged = git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
    .split("\0").filter(Boolean);
  if (staged.length > 0) return staged;
  return git(["ls-files", "-z"]).split("\0").filter(Boolean);
}

export async function checkSecrets(root = process.cwd()): Promise<SecretFinding[]> {
  const findings: SecretFinding[] = [];
  for (const path of repositoryFiles(root)) {
    let content: string;
    try { content = await readFile(resolve(root, path), "utf8"); } catch { continue; }
    if (content.includes("\0")) continue;
    for (const finding of findSecrets(content)) findings.push({ ...finding, label: `${path}: ${finding.label}` });
  }
  return findings;
}

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks).toString("utf8");
}

export async function main(argv = process.argv.slice(2)): Promise<number> {
  if (argv[0] === "check-secrets") {
    const findings = await checkSecrets();
    for (const finding of findings) console.error(`${finding.label}:${finding.line}: ${finding.match}`);
    return findings.length === 0 ? 0 : 1;
  }
  if (argv[0] === "hook") {
    const input = await readStdin();
    let event: unknown;
    try { event = JSON.parse(input); } catch { console.error("agent-guard: hook input must be JSON"); return 2; }
    const findings = inspectHookEvent(event);
    if (findings.length) console.log(JSON.stringify({ decision: "deny", reason: "potential secret detected" }));
    else console.log(JSON.stringify({ decision: "allow" }));
    return findings.length ? 1 : 0;
  }
  console.error("usage: agent-guard <hook|check-secrets>");
  return 2;
}

const invokedDirectly = process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname);
if (invokedDirectly) process.exitCode = await main();
