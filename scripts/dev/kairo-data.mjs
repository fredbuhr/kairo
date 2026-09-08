#!/usr/bin/env node
import path from "node:path";
import {
  createKairoDataBackup,
  restoreKairoDataBackup,
  verifyKairoDataBackup,
} from "../../packages/kairo-core/src/index.js";

function usage() {
  console.error(`Usage:
  node scripts/dev/kairo-data.mjs backup [backup-dir]
  node scripts/dev/kairo-data.mjs verify <backup-dir>
  node scripts/dev/kairo-data.mjs restore <backup-dir> <new-target-data-dir>

backup uses KAIRO_DATA_DIR as its source and defaults to KAIRO_DEV_ROOT/backups/<timestamp>.
restore is intentionally non-overwriting: the target path must not already exist.`);
}

function timestampName() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function requireEnv(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required. Source scripts/dev/openclaw-env.sh first.`);
  return value;
}

async function main() {
  const [command, ...args] = process.argv.slice(2);
  if (command === "backup") {
    const dataDir = requireEnv("KAIRO_DATA_DIR");
    const devRoot = process.env.KAIRO_DEV_ROOT?.trim() || path.dirname(dataDir);
    const backupDir = path.resolve(args[0] ?? path.join(devRoot, "backups", `kairo-data-${timestampName()}`));
    const manifest = await createKairoDataBackup({ dataDir, backupDir });
    console.log(JSON.stringify({ ok: true, action: "backup", backupDir, manifest }, null, 2));
    return;
  }

  if (command === "verify") {
    if (args.length !== 1) {
      usage();
      process.exitCode = 2;
      return;
    }
    const backupDir = path.resolve(args[0]);
    const manifest = await verifyKairoDataBackup({ backupDir });
    console.log(JSON.stringify({ ok: true, action: "verify", backupDir, manifest }, null, 2));
    return;
  }

  if (command === "restore") {
    if (args.length !== 2) {
      usage();
      process.exitCode = 2;
      return;
    }
    const backupDir = path.resolve(args[0]);
    const targetDataDir = path.resolve(args[1]);
    const manifest = await restoreKairoDataBackup({ backupDir, targetDataDir });
    console.log(JSON.stringify({ ok: true, action: "restore", backupDir, targetDataDir, manifest }, null, 2));
    return;
  }

  usage();
  process.exitCode = 2;
}

main().catch((error) => {
  console.error(JSON.stringify({
    ok: false,
    error: error instanceof Error ? error.message : String(error),
    code: error && typeof error === "object" && "code" in error ? error.code : undefined,
  }, null, 2));
  process.exitCode = 1;
});
