// Loads EXTENSION/webview/interface.js, takes the SIM_ENGINE_JS it sends with
// $se("runCode", ...), removes its newlines the way PT's webview -> Script
// Engine IPC does, runs it against a stub ipc, and prints as JSON what the
// installed mcpDemoDevices() returns (or the error).
//
//   node interface_sim_engine_harness.js <interface.js>
//
// Used by tests/test_webview_sim_engine.py. interface.js itself is never
// changed to suit the harness.
"use strict";
const fs = require("fs");
const vm = require("vm");

const [scriptPath] = process.argv.slice(2);

const document = {
    addEventListener: () => {},
    getElementById: () => null,
    querySelectorAll: () => [],
};
const navigator = { platform: "MacIntel", userAgent: "" };
const page = { document, navigator, console, setTimeout: () => 1, clearTimeout: () => {} };
vm.createContext(page);
vm.runInContext(fs.readFileSync(scriptPath, "utf8"), page, { filename: scriptPath });

const sent = String(page.SIM_ENGINE_JS);
const received = sent.replace(/\r?\n/g, " ");

function device(name, model) {
    return { getName: () => name, getModel: () => model, getCommandPrompt: () => ({}) };
}
const devices = [device("PC2", "PC-PT"), device("Srv", "Server-PT"), device("PC1", "PC-PT")];
const engine = {
    console,
    ipc: {
        network: () => ({ getDeviceCount: () => devices.length, getDeviceAt: (i) => devices[i] }),
        appWindow: () => ({ isSimulationMode: () => true }),
    },
};
engine.GLOBAL = engine;
vm.createContext(engine);

let out;
try {
    vm.runInContext(received, engine);
    out = { newlines: (sent.match(/\n/g) || []).length,
            devices: JSON.parse(engine.mcpDemoDevices()) };
} catch (e) {
    out = { newlines: (sent.match(/\n/g) || []).length, error: String(e) };
}
process.stdout.write(JSON.stringify(out));
