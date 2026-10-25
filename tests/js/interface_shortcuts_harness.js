// Loads EXTENSION/webview/interface.js in a sandbox with a stub navigator and
// document, presses keys at the editor and the page, and prints as JSON which
// actions ran and what the shortcut hints read.
//
//   node interface_shortcuts_harness.js <interface.js> '<scenario json>'
//   scenario: {"platform": "MacIntel", "userAgent": "...",
//              "keys": [{"key": "k", "metaKey": true}, ...]}
//
// Used by tests/test_webview_shortcuts.py. interface.js itself is never changed
// to suit the harness.
"use strict";
const fs = require("fs");
const vm = require("vm");

const [scriptPath, scenarioJson] = process.argv.slice(2);
const scenario = JSON.parse(scenarioJson);

function element(attrs) {
    return {
        textContent: attrs.text || "",
        title: attrs.title || "",
        getAttribute: (name) => (name in attrs ? attrs[name] : null),
    };
}

// The hints as index.html marks them.
const hints = {
    runKbd: element({ "data-shortcut": "run", text: "Ctrl+Enter" }),
    clearKbd: element({ "data-shortcut": "clear", text: "Ctrl+K" }),
    runBtn: element({ "data-shortcut-title": "run", "data-title": "Run", title: "Run (Ctrl+Enter)" }),
    clearLogBtn: element({ "data-shortcut-title": "clearLog", "data-title": "Clear log", title: "Clear log (Ctrl+L)" }),
};
const editor = { value: "x", selectionStart: 1, selectionEnd: 1 };
const listeners = [];
const document = {
    addEventListener: (type, fn) => { if (type === "keydown") listeners.push(fn); },
    getElementById: (id) => (id === "codeeditor" ? editor : null),
    querySelectorAll: (sel) => {
        if (sel === "[data-shortcut]") return [hints.runKbd, hints.clearKbd];
        if (sel === "[data-shortcut-title]") return [hints.runBtn, hints.clearLogBtn];
        return [];
    },
};
const navigator = { platform: scenario.platform || "", userAgent: scenario.userAgent || "" };
const context = { document, navigator, console, setTimeout: () => 1, clearTimeout: () => {} };
vm.createContext(context);
vm.runInContext(fs.readFileSync(scriptPath, "utf8"), context, { filename: scriptPath });

// Record the actions instead of running them (function declarations are
// globals of the context, so the handlers pick these up).
let ran = [];
context.executeCode = () => ran.push("run");
context.clearEditor = () => ran.push("clear");
context.clearLog = () => ran.push("clearLog");

const pressed = [];
for (const k of scenario.keys || []) {
    const e = Object.assign({ ctrlKey: false, metaKey: false, altKey: false, shiftKey: false,
                              preventDefault: () => {} }, k);
    ran = [];
    context.editorKeyDown(e);
    for (const fn of listeners) fn(e);
    pressed.push(ran);
}

context.applyShortcutLabels(context.IS_MAC);
process.stdout.write(JSON.stringify({
    isMac: context.IS_MAC,
    pressed,
    hints: {
        runKbd: hints.runKbd.textContent,
        clearKbd: hints.clearKbd.textContent,
        runTitle: hints.runBtn.title,
        clearLogTitle: hints.clearLogBtn.title,
    },
}));
