import {
  mkdir,
  open,
  readdir,
  readFile,
  rename,
  unlink,
  stat,
} from "node:fs/promises";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { canonicalJson } from "./canonical.js";
import type { WireEvent } from "./event.js";

export class Spool {
  constructor(
    readonly directory: string,
    readonly maxBytes: number,
  ) {}

  async append(events: WireEvent[]): Promise<void> {
    if (!events.length) return;
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    const path = join(
      this.directory,
      `spool-${Date.now()}-${randomUUID()}.jsonl`,
    );
    const temporary = path + ".pending";
    const handle = await open(temporary, "wx", 0o600);
    try {
      await handle.writeFile(
        events.map((event) => canonicalJson(event)).join("\n") + "\n",
      );
      await handle.sync();
    } finally {
      await handle.close();
    }
    await rename(temporary, path);
    const files = (await readdir(this.directory))
      .filter((name) => name.startsWith("spool-") && name.endsWith(".jsonl"))
      .sort();
    const sizes = await Promise.all(
      files.map(async (name) => ({
        name,
        bytes:
          (await tolerateMissing(() => stat(join(this.directory, name))))
            ?.size ?? 0,
      })),
    );
    let total = sizes.reduce((sum, file) => sum + file.bytes, 0);
    for (const file of sizes) {
      if (total <= this.maxBytes) break;
      await tolerateMissing(() => unlink(join(this.directory, file.name)));
      total -= file.bytes;
      console.warn(`tracelore_spool_limit dropped_bytes=${file.bytes}`);
    }
  }

  async drain(
    send: (events: WireEvent[]) => Promise<boolean>,
    batchSize: number,
  ): Promise<void> {
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    for (const name of (await readdir(this.directory))
      .filter((name) => name.startsWith("spool-") && name.endsWith(".jsonl"))
      .sort()) {
      const path = join(this.directory, name);
      const content = await tolerateMissing(() => readFile(path, "utf8"));
      if (content === undefined) continue;
      const lines = content.split("\n");
      lines.pop();
      const events = lines.map((line) => JSON.parse(line) as WireEvent);
      for (let index = 0; index < events.length; index += batchSize) {
        if (!(await send(events.slice(index, index + batchSize)))) return;
      }
      await tolerateMissing(() => unlink(path));
    }
  }

  async reject(events: WireEvent[]): Promise<void> {
    const rejected = join(this.directory, "rejected");
    await new Spool(rejected, this.maxBytes).append(events);
  }
}

async function tolerateMissing<T>(
  operation: () => Promise<T>,
): Promise<T | undefined> {
  try {
    return await operation();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
  }
}
