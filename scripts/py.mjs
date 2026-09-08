#!/usr/bin/env node
/**
 * Cross-platform Python launcher for the npm scripts.
 *
 * `python3` is the right command on Linux and macOS and does not exist on a
 * standard Windows install, where the interpreter is `python` and the version
 * launcher is `py`. Hardcoding either one makes `npm run seed` fail for half of
 * the people who clone this repository, so the interpreter is resolved at run
 * time instead.
 *
 * Resolution requires Python >= 3.10, because the backend uses PEP 604 unions
 * and `match` statements. A `python` that turns out to be 3.9, or the Windows
 * Store stub that exits non-zero, is skipped rather than reported as a
 * confusing syntax error hundreds of lines into an import.
 *
 * Usage:
 *   node scripts/py.mjs [--cwd <dir>] <python args...>
 */

import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const MIN = [3, 10];

/** Candidate commands, most likely first for the current platform. */
const CANDIDATES =
  process.platform === "win32"
    ? [
        ["py", ["-3"]],
        ["python", []],
        ["python3", []],
      ]
    : [
        ["python3", []],
        ["python", []],
      ];

/**
 * @returns {[string, string[]]|null} the command and any prefix arguments,
 *   or null when no suitable interpreter is installed.
 */
export function resolvePython() {
  const probe = `import sys; sys.exit(0 if sys.version_info >= (${MIN[0]}, ${MIN[1]}) else 1)`;
  for (const [cmd, pre] of CANDIDATES) {
    let result;
    try {
      result = spawnSync(cmd, [...pre, "-c", probe], { stdio: "ignore" });
    } catch {
      continue;
    }
    if (result.error || result.status !== 0) continue;
    return [cmd, pre];
  }
  return null;
}

/** Print an actionable message and exit; called when no interpreter is found. */
export function failNoPython() {
  const want = MIN.join(".");
  console.error(
    [
      "",
      `LandTrust Connect needs Python ${want} or newer and could not find it.`,
      "",
      process.platform === "win32"
        ? [
            "  Install it from https://www.python.org/downloads/ and tick",
            '  "Add python.exe to PATH" in the first screen of the installer,',
            "  then open a NEW terminal so the change takes effect.",
          ].join("\n")
        : [
            "  macOS:  brew install python@3.12",
            "  Ubuntu: sudo apt install python3 python3-pip python3-venv",
          ].join("\n"),
      "",
      `Tried: ${CANDIDATES.map(([c, p]) => [c, ...p].join(" ")).join(", ")}`,
      "",
    ].join("\n"),
  );
  process.exit(1);
}

function main() {
  const argv = process.argv.slice(2);
  let cwd = ROOT;
  if (argv[0] === "--cwd") {
    cwd = path.resolve(ROOT, argv[1]);
    argv.splice(0, 2);
  }

  const found = resolvePython();
  if (!found) failNoPython();
  const [cmd, pre] = found;

  const run = spawnSync(cmd, [...pre, ...argv], { stdio: "inherit", cwd });
  if (run.error) {
    console.error(`Failed to start ${cmd}: ${run.error.message}`);
    process.exit(1);
  }
  // A signalled child reports status null; treat that as a failure exit.
  process.exit(run.status === null ? 1 : run.status);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
