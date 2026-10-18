import { readFile } from "node:fs/promises";
import { test } from "node:test";
import assert from "node:assert/strict";
import { canonicalJson, eventHash } from "../dist/canonical.js";
import { createHash } from "node:crypto";
const vectors = JSON.parse(
  await readFile(
    new URL("../../../docs/hash_vectors.json", import.meta.url),
    "utf8",
  ),
);
for (const vector of vectors)
  test(vector.name, () => {
    const actual =
      vector.kind === "event"
        ? eventHash(vector.value)
        : createHash("sha256")
            .update(canonicalJson(vector.value))
            .digest("hex");
    assert.equal(actual, vector.sha256);
  });
