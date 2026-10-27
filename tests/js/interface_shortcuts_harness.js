// Loads EXTENSION/webview/interface.js in a sandbox with a stub navigator and
// document, presses keys in the console, and prints as JSON which
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
    runHint: element({ "data-shortcut": "run", text: "Ctrl+Enter" }),
    runBtn: element({ "data-shortcut-title": "run", "data-title": "Run", title: "Run (Ctrl+Enter)" }),
    clearBtn: element({ "data-shortcut-title": "clear", "data-title": "Clear", title: "Clear (Ctrl+K)" }),
};
const editor = { value: "x", selectionStart: 1, selectionEnd: 1 };
const listeners = [];
const document = {
    addEventListener: (type, fn) => { if (type === "keydown") listeners.push(fn); },
    getElementById: (id) => (id === "code" ? editor : null),
    querySelectorAll: (sel) => {
        if (sel === "[data-shortcut]") return [hints.runHint];
        if (sel === "[data-shortcut-title]") return [hints.runBtn, hints.clearBtn];
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
context.runConsole = () => ran.push("run");
context.clearCode = () => ran.push("clear");

const pressed = [];
for (const k of scenario.keys || []) {
    const e = Object.assign({ ctrlKey: false, metaKey: false, altKey: false, shiftKey: false,
                              preventDefault: () => {} }, k);
    ran = [];
    context.consoleKeyDown(e);
    for (const fn of listeners) fn(e);
    pressed.push(ran);
}

context.applyShortcutLabels(context.IS_MAC);
process.stdout.write(JSON.stringify({
    isMac: context.IS_MAC,
    pressed,
    hints: {
        runHint: hints.runHint.textContent,
        runTitle: hints.runBtn.title,
        clearTitle: hints.clearBtn.title,
    },
}));
