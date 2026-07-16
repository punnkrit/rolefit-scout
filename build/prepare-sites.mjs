import { cp, mkdir, readdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const dist = new URL("../dist/", import.meta.url);

async function removeLocalSecretFiles(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      await removeLocalSecretFiles(new URL(`${entry.name}/`, directory));
    } else if (entry.name === ".dev.vars") {
      await rm(fileURLToPath(new URL(entry.name, directory)), { force: true });
    }
  }
}

await removeLocalSecretFiles(dist);
await mkdir(new URL("server/", dist), { recursive: true });
await cp(new URL("rolefit_scout/index.js", dist), new URL("server/index.js", dist));
