import { createHash } from "node:crypto";
import {
  copyFile,
  lstat,
  mkdir,
  readFile,
  readdir,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { KairoError } from "./errors.js";

const BACKUP_SCHEMA_VERSION = 1;
const BACKUP_TYPE = "kairo_data_backup";

function requirePath(value, label) {
  const text = String(value ?? "").trim();
  if (!text) throw new TypeError(`${label} is required.`);
  return path.resolve(text);
}

async function pathExists(filePath) {
  try {
    await lstat(filePath);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

function isWithin(parentPath, childPath) {
  const relative = path.relative(parentPath, childPath);
  return relative !== "" && !relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative);
}

function safeRelativePath(value) {
  if (typeof value !== "string" || !value || value.includes("\0")) {
    throw new KairoError("INVALID_BACKUP", "Backup manifest contains an invalid file path.");
  }
  const posix = value.replaceAll("\\", "/");
  if (posix.startsWith("/") || posix.split("/").some((segment) => segment === ".." || segment === "")) {
    throw new KairoError("INVALID_BACKUP", `Backup manifest path '${value}' is unsafe.`);
  }
  return posix;
}

async function listRegularFiles(rootDir) {
  const files = [];

  async function visit(currentDir, prefix = "") {
    const entries = await readdir(currentDir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
      const fullPath = path.join(currentDir, entry.name);
      if (entry.isSymbolicLink()) {
        throw new KairoError("UNSAFE_DATA_ENTRY", `Refusing symbolic link '${relative}' in KAIRO data.`);
      }
      if (entry.isDirectory()) {
        await visit(fullPath, relative);
        continue;
      }
      if (!entry.isFile()) {
        throw new KairoError("UNSAFE_DATA_ENTRY", `Refusing non-regular file '${relative}' in KAIRO data.`);
      }
      files.push(relative);
    }
  }

  await visit(rootDir);
  return files;
}

async function sha256File(filePath) {
  const content = await readFile(filePath);
  return {
    size: content.byteLength,
    sha256: createHash("sha256").update(content).digest("hex"),
  };
}

function validateManifest(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new KairoError("INVALID_BACKUP", "Backup manifest must be an object.");
  }
  if (value.schema_version !== BACKUP_SCHEMA_VERSION || value.type !== BACKUP_TYPE) {
    throw new KairoError("INVALID_BACKUP", "Unsupported KAIRO backup manifest.");
  }
  if (typeof value.created_at !== "string" || !value.created_at.trim()) {
    throw new KairoError("INVALID_BACKUP", "Backup manifest is missing created_at.");
  }
  if (!Array.isArray(value.files)) {
    throw new KairoError("INVALID_BACKUP", "Backup manifest files must be an array.");
  }
  if (value.file_count !== value.files.length) {
    throw new KairoError("INVALID_BACKUP", "Backup manifest file_count does not match files.");
  }

  const seen = new Set();
  const files = value.files.map((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      throw new KairoError("INVALID_BACKUP", "Backup manifest contains an invalid file entry.");
    }
    const relative = safeRelativePath(entry.path);
    if (seen.has(relative)) {
      throw new KairoError("INVALID_BACKUP", `Backup manifest duplicates '${relative}'.`);
    }
    seen.add(relative);
    if (!Number.isInteger(entry.size) || entry.size < 0) {
      throw new KairoError("INVALID_BACKUP", `Backup manifest has invalid size for '${relative}'.`);
    }
    if (typeof entry.sha256 !== "string" || !/^[a-f0-9]{64}$/i.test(entry.sha256)) {
      throw new KairoError("INVALID_BACKUP", `Backup manifest has invalid sha256 for '${relative}'.`);
    }
    return { path: relative, size: entry.size, sha256: entry.sha256.toLowerCase() };
  });

  return {
    schema_version: BACKUP_SCHEMA_VERSION,
    type: BACKUP_TYPE,
    created_at: value.created_at,
    file_count: files.length,
    files,
  };
}

async function verifyFiles(rootDir, manifest) {
  const actualFiles = await listRegularFiles(rootDir);
  const expected = manifest.files.map((entry) => entry.path);
  if (actualFiles.length !== expected.length || actualFiles.some((file, index) => file !== expected[index])) {
    throw new KairoError("BACKUP_INTEGRITY", "Backup file set does not match its manifest.");
  }

  for (const entry of manifest.files) {
    const actual = await sha256File(path.join(rootDir, ...entry.path.split("/")));
    if (actual.size !== entry.size || actual.sha256 !== entry.sha256) {
      throw new KairoError("BACKUP_INTEGRITY", `Backup integrity check failed for '${entry.path}'.`);
    }
  }
}

export async function createKairoDataBackup({ dataDir, backupDir, clock = () => new Date() }) {
  const source = requirePath(dataDir, "dataDir");
  const target = requirePath(backupDir, "backupDir");
  if (source === target || isWithin(source, target)) {
    throw new KairoError("UNSAFE_BACKUP_TARGET", "backupDir must be outside KAIRO dataDir.");
  }
  if (await pathExists(target)) {
    throw new KairoError("BACKUP_TARGET_EXISTS", `Backup target already exists: ${target}`);
  }
  const sourceStat = await stat(source).catch((error) => {
    if (error?.code === "ENOENT") {
      throw new KairoError("DATA_DIR_NOT_FOUND", `KAIRO dataDir does not exist: ${source}`);
    }
    throw error;
  });
  if (!sourceStat.isDirectory()) {
    throw new KairoError("INVALID_DATA_DIR", `KAIRO dataDir is not a directory: ${source}`);
  }

  const temp = `${target}.tmp-${process.pid}-${Math.random().toString(16).slice(2)}`;
  try {
    await mkdir(path.join(temp, "data"), { recursive: true });
    const relativeFiles = await listRegularFiles(source);
    const files = [];
    for (const relative of relativeFiles) {
      const sourceFile = path.join(source, ...relative.split("/"));
      const destinationFile = path.join(temp, "data", ...relative.split("/"));
      await mkdir(path.dirname(destinationFile), { recursive: true });
      await copyFile(sourceFile, destinationFile);
      const digest = await sha256File(destinationFile);
      files.push({ path: relative, ...digest });
    }

    const manifest = {
      schema_version: BACKUP_SCHEMA_VERSION,
      type: BACKUP_TYPE,
      created_at: clock().toISOString(),
      file_count: files.length,
      files,
    };
    await writeFile(path.join(temp, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
    await mkdir(path.dirname(target), { recursive: true });
    await rename(temp, target);
    return manifest;
  } catch (error) {
    await rm(temp, { recursive: true, force: true }).catch(() => {});
    throw error;
  }
}

export async function verifyKairoDataBackup({ backupDir }) {
  const backup = requirePath(backupDir, "backupDir");
  const manifestPath = path.join(backup, "manifest.json");
  let parsed;
  try {
    parsed = JSON.parse(await readFile(manifestPath, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") {
      throw new KairoError("INVALID_BACKUP", `Backup manifest is missing: ${manifestPath}`);
    }
    if (error instanceof SyntaxError) {
      throw new KairoError("INVALID_BACKUP", "Backup manifest is not valid JSON.");
    }
    throw error;
  }
  const manifest = validateManifest(parsed);
  await verifyFiles(path.join(backup, "data"), manifest);
  return manifest;
}

export async function restoreKairoDataBackup({ backupDir, targetDataDir }) {
  const backup = requirePath(backupDir, "backupDir");
  const target = requirePath(targetDataDir, "targetDataDir");
  if (backup === target || isWithin(backup, target)) {
    throw new KairoError("UNSAFE_RESTORE_TARGET", "targetDataDir must be outside the backup directory.");
  }
  if (await pathExists(target)) {
    throw new KairoError(
      "RESTORE_TARGET_EXISTS",
      `Restore target already exists; move it aside before restoring: ${target}`,
    );
  }

  const manifest = await verifyKairoDataBackup({ backupDir: backup });
  const temp = `${target}.tmp-${process.pid}-${Math.random().toString(16).slice(2)}`;
  try {
    await mkdir(temp, { recursive: true });
    for (const entry of manifest.files) {
      const sourceFile = path.join(backup, "data", ...entry.path.split("/"));
      const destinationFile = path.join(temp, ...entry.path.split("/"));
      await mkdir(path.dirname(destinationFile), { recursive: true });
      await copyFile(sourceFile, destinationFile);
    }
    await verifyFiles(temp, manifest);
    await mkdir(path.dirname(target), { recursive: true });
    await rename(temp, target);
    return manifest;
  } catch (error) {
    await rm(temp, { recursive: true, force: true }).catch(() => {});
    throw error;
  }
}
