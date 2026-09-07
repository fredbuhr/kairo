import { cp, mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const here = dirname(fileURLToPath(import.meta.url));
const pluginDir = resolve(here, "..");
const repoRoot = resolve(pluginDir, "../..");
const coreDir = join(repoRoot, "packages", "kairo-core");
const stageRoot = await mkdtemp(join(tmpdir(), "kairo-openclaw-pack-"));
const stageDir = join(stageRoot, "package");

try {
  await mkdir(join(stageDir, "node_modules", "@kairo"), { recursive: true });

  for (const entry of ["dist", "openclaw.plugin.json", "README.md"]) {
    await cp(join(pluginDir, entry), join(stageDir, entry), { recursive: true });
  }

  await cp(coreDir, join(stageDir, "node_modules", "@kairo", "core"), {
    recursive: true,
    filter: (source) => !source.includes("node_modules") && !source.endsWith(".tgz"),
  });

  const manifest = JSON.parse(await readFile(join(pluginDir, "package.json"), "utf8"));
  manifest.dependencies["@kairo/core"] = "0.1.0";
  delete manifest.scripts["plugin:pack"];
  await writeFile(join(stageDir, "package.json"), `${JSON.stringify(manifest, null, 2)}\n`);

  const output = execFileSync(
    "npm",
    ["pack", stageDir, "--pack-destination", pluginDir, "--silent"],
    { cwd: pluginDir, encoding: "utf8" },
  ).trim();

  console.log(basename(output));
} finally {
  await rm(stageRoot, { recursive: true, force: true });
}
