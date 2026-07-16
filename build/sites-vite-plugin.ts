import { access, cp, mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin } from "vite";

async function exists(path: string) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

export function sites(): Plugin {
  let root = process.cwd();
  return {
    name: "sites",
    apply: "build",
    configResolved(config) {
      root = config.root;
    },
    async closeBundle() {
      const outputDirectory = resolve(root, "dist", ".openai");
      const hostingConfig = resolve(root, ".openai", "hosting.json");
      const cloudflareWorker = resolve(root, "dist", "worker", "index.js");
      const sitesWorker = resolve(root, "dist", "server", "index.js");
      await rm(outputDirectory, { recursive: true, force: true });
      await mkdir(outputDirectory, { recursive: true });
      if (await exists(cloudflareWorker)) {
        await mkdir(resolve(root, "dist", "server"), { recursive: true });
        await cp(cloudflareWorker, sitesWorker);
      }
      if (await exists(hostingConfig)) {
        await cp(hostingConfig, resolve(outputDirectory, "hosting.json"));
      }
    }
  };
}
