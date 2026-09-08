#!/usr/bin/env node
/**
 * Installs the backend's Python dependencies.
 *
 * `--break-system-packages` is required on Debian/Ubuntu and recent macOS
 * Homebrew installs, where PEP 668 marks the system interpreter as externally
 * managed and pip refuses to touch it. It is unnecessary everywhere else and
 * is rejected outright by pip older than 23.0, so the flag is attempted first
 * and dropped on failure rather than being demanded of every user.
 *
 * If a virtual environment is active (VIRTUAL_ENV set), the flag is skipped
 * entirely — PEP 668 does not apply inside one, and passing it would be noise.
 */

import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { resolvePython, failNoPython } from "./py.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REQUIREMENTS = path.join(ROOT, "backend", "requirements.txt");

const found = resolvePython();
if (!found) failNoPython();
const [cmd, pre] = found;

function pipInstall(extra) {
  return spawnSync(cmd, [...pre, "-m", "pip", "install", "-r", REQUIREMENTS, ...extra], {
    stdio: "inherit",
    cwd: ROOT,
  });
}

const inVenv = Boolean(process.env.VIRTUAL_ENV);

let run = pipInstall(inVenv ? [] : ["--break-system-packages"]);

if (!inVenv && run.status !== 0) {
  // Either pip is too old to know the flag, or the install genuinely failed.
  // Retrying without it distinguishes the two and fixes the first.
  console.log("\nRetrying without --break-system-packages…\n");
  run = pipInstall([]);
}

if (run.status !== 0) {
  console.error(
    "\nInstalling the backend dependencies failed. If this is a permissions error, " +
      "create a virtual environment first:\n" +
      `  ${[cmd, ...pre].join(" ")} -m venv .venv\n` +
      (process.platform === "win32"
        ? "  .venv\\Scripts\\activate\n"
        : "  source .venv/bin/activate\n") +
      "  npm run setup\n",
  );
}

process.exit(run.status === null ? 1 : run.status);
