// Loads EXTENSION/script-engine/main.js in a sandbox with a stub PT `ipc` and an
// in-memory file set, then prints what its path functions answer as JSON.
//
//   node main_paths_harness.js <main.js> '<scenario json>'
//   scenario: {"userFolder": "...", "files": ["/abs/path", ...]}
//
// Used by tests/test_main_js_paths.py. It stubs only what main.js touches when
// these functions run; main.js itself is never changed to suit the harness.
"use strict";
const fs = require("fs");
const vm = require("vm");

const [mainPath, scenarioJson] = process.argv.slice(2);
const scenario = JSON.parse(scenarioJson);
const files = new Set(scenario.files || []);
const dirs = new Set();
for (const f of files) {
    let d = f;
    while (d.lastIndexOf("/") > 0) {
        d = d.substring(0, d.lastIndexOf("/"));
        dirs.add(d);
    }
}

const fm = {
    fileExists: (p) => files.has(p),
    getFileContents: (p) => (files.has(p) ? "t".repeat(43) : ""),
    directoryExists: (p) => dirs.has(p),
    makeDirectory: (p) => { dirs.add(p); return true; },
    writePlainTextToFile: () => true,
    getFilesInDirectory: () => [],
    getFileModificationTime: () => 0,
    removeFile: () => true,
};
const ipc = {
    appWindow: () => ({ getUserFolder: () => scenario.userFolder }),
    systemFileManager: () => fm,
};
const context = { ipc, setTimeout: () => 1, clearTimeout: () => {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync(mainPath, "utf8"), context, { filename: "main.js" });

const out = {
    candidates: Array.from(context.mcpTokenCandidates()),
    bridgeDir: context.mcpBridgeDir(),
};
context.fileBridgeTick();
out.cachedAfterTick = vm.runInContext("_fileBridgeDir", context);
process.stdout.write(JSON.stringify(out));
