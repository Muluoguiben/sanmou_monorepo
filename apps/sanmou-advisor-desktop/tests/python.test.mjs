import assert from "node:assert/strict";
import { test } from "node:test";
import path from "node:path";
import { probePython, selectPython } from "../dist-electron/python.js";

const repo = path.resolve("../..");
test("R03 missing executable returns diagnostic instead of throwing", () => {
  const result = probePython({ command: path.join(repo, "missing-python-r03"), args: [], label: "missing" }, process.env, repo);
  assert.equal(result.ok, false);
  assert.match(result.detail, /ENOENT/);
});

test("R03 deleted PYTHON falls back to a working installed candidate", () => {
  const original = process.env.PYTHON;
  process.env.PYTHON = path.join(repo, "deleted-venv-r03", "python.exe");
  try {
    const env = { ...process.env, PYTHONPATH: ["pioneer-agent", "sanmou-common", "qa-agent"].map(p => path.join(repo, "packages", p, "src")).join(path.delimiter) };
    const selected = selectPython(repo, env);
    assert.equal(selected.ok, true, selected.detail);
    assert.notEqual(selected.candidate.command, process.env.PYTHON);
  } finally {
    if (original === undefined) delete process.env.PYTHON;
    else process.env.PYTHON = original;
  }
});
