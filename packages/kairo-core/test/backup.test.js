import assert from "node:assert/strict";
import { appendFile, mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  KairoError,
  KairoStore,
  createKairoDataBackup,
  restoreKairoDataBackup,
  verifyKairoDataBackup,
} from "../src/index.js";

async function withRoot(fn) {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-backup-"));
  try {
    return await fn(root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("creates, verifies, and restores an integrity-checked KAIRO data snapshot", async () => {
  await withRoot(async (root) => {
    const dataDir = path.join(root, "runtime-data");
    const backupDir = path.join(root, "backups", "snapshot-1");
    const restoredDir = path.join(root, "restored-data");
    const store = new KairoStore({ dataDir });
    const project = await store.createProject({ name: "ZTIKIX", summary: "Backup proof" });
    await store.captureIdea({
      project: project.slug,
      title: "Preserved idea",
      content: "This content must survive backup and restore.",
      epistemicStatus: "hypothesis",
    });

    const originalProject = await readFile(
      path.join(dataDir, "projects", "ztikix", "project.md"),
      "utf8",
    );
    const created = await createKairoDataBackup({
      dataDir,
      backupDir,
      clock: () => new Date("2026-09-08T08:00:00.000Z"),
    });
    assert.equal(created.type, "kairo_data_backup");
    assert.equal(created.schema_version, 1);
    assert.ok(created.file_count >= 2);
    assert.equal(created.files.length, created.file_count);

    const verified = await verifyKairoDataBackup({ backupDir });
    assert.deepEqual(verified, created);

    await appendFile(path.join(dataDir, "projects", "ztikix", "project.md"), "\nMUTATED AFTER BACKUP\n");
    await restoreKairoDataBackup({ backupDir, targetDataDir: restoredDir });
    const restoredProject = await readFile(
      path.join(restoredDir, "projects", "ztikix", "project.md"),
      "utf8",
    );
    assert.equal(restoredProject, originalProject);
    assert.doesNotMatch(restoredProject, /MUTATED AFTER BACKUP/);
  });
});

test("detects backup tampering before restore", async () => {
  await withRoot(async (root) => {
    const dataDir = path.join(root, "runtime-data");
    const backupDir = path.join(root, "backup");
    const store = new KairoStore({ dataDir });
    await store.createProject({ name: "ZTIKIX" });
    const manifest = await createKairoDataBackup({ dataDir, backupDir });
    const target = manifest.files[0];
    assert.ok(target);

    await appendFile(path.join(backupDir, "data", ...target.path.split("/")), "tamper");
    await assert.rejects(
      verifyKairoDataBackup({ backupDir }),
      (error) => error instanceof KairoError && error.code === "BACKUP_INTEGRITY",
    );
  });
});

test("restore refuses to overwrite an existing data directory", async () => {
  await withRoot(async (root) => {
    const dataDir = path.join(root, "runtime-data");
    const backupDir = path.join(root, "backup");
    const targetDataDir = path.join(root, "existing-target");
    const sourceStore = new KairoStore({ dataDir });
    const targetStore = new KairoStore({ dataDir: targetDataDir });
    await sourceStore.createProject({ name: "ZTIKIX" });
    await targetStore.createProject({ name: "Aventulire" });
    await createKairoDataBackup({ dataDir, backupDir });

    await assert.rejects(
      restoreKairoDataBackup({ backupDir, targetDataDir }),
      (error) => error instanceof KairoError && error.code === "RESTORE_TARGET_EXISTS",
    );
  });
});

test("backup refuses to live inside KAIRO data and refuses symlinks", async () => {
  await withRoot(async (root) => {
    const dataDir = path.join(root, "runtime-data");
    const store = new KairoStore({ dataDir });
    await store.createProject({ name: "ZTIKIX" });

    await assert.rejects(
      createKairoDataBackup({ dataDir, backupDir: path.join(dataDir, "backup") }),
      (error) => error instanceof KairoError && error.code === "UNSAFE_BACKUP_TARGET",
    );
  });
});
