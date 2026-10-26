// ============================================================================
// PT-MCP Builder Interface v5
// Premium Control Center — Editor, Terminal, Status Dashboard, Quick Build
// ============================================================================

// ------------------------------------------------------------------ State ---

var S = {
    // Connection
    bridgeUp:      false,
    ptConnected:   false,
    lastPollAgo:   null,
    commandCount:  0,
    lastActivity:  null,
    sessionStart:  Date.now(),

    // UI
    activeTab:     "editor",
    errCount:      0,

    // Logs
    logs:          [],       // { ts, type, msg } objects
    logFilter:     "all",
    maxLogs:       500,

    // History
    history:       [],       // string[] — ring buffer of 20 scripts
    historyPos:    -1,       // navigator position

    // Sparkline
    pollTimes:     [],       // timestamps of successful polls (last 20)

    // Editor auto-save debounce
    _saveTimer:    null,
};

var BRIDGE_BASE = "http://127.0.0.1:54321";

// Token shared with the MCP server. This webview runs under the this-sm:
// scheme and has no file system access, so it cannot read the token from
// disk: it asks the Script Engine for it with $se("getMcpToken"), which can read
// files. No pairing or user action is needed. It is deliberately not cached
// (if the server rotates the token, the copy would silently go stale).
var S_TOKEN = "";

function bridgeUrl(path) {
    return BRIDGE_BASE + path + (S_TOKEN ? "?t=" + encodeURIComponent(S_TOKEN) : "");
}

function bootstrapSnippet() {
    var q = encodeURIComponent(S_TOKEN);
    return '/* PT-MCP Bridge */ window.webview.evaluateJavaScriptAsync(' +
        '"setInterval(function(){var x=new XMLHttpRequest();' +
        "x.open('GET','http://127.0.0.1:54321/next?t=" + q + "',true);" +
        'x.onload=function(){if(x.status===200&&x.responseText)' +
        // try/catch: without it, an error inside runCode opens a PT modal that
        // freezes the webview and kills the polling. The other copies of the bootstrap
        // already had it; this one had fallen behind.
        "{try{$se('runCode',x.responseText)}catch(e){}}};x.onerror=function(){};" +
        'x.send()},500)");';
}

function refreshBootstrapSnippet() {
    var el = document.getElementById("bootstrapSnippet");
    if (el) el.textContent = bootstrapSnippet();
}

/* Loads the token from the Script Engine, which reads it from disk.
   The webview cannot touch files; the Script Engine can. $se() returns a
   Promise. No pairing or user action is needed: the extension starts and
   works. */
function loadToken(onDone) {
    try {
        $se("getMcpToken").then(function(tok) {
            if (tok) {
                S_TOKEN = String(tok);
                refreshBootstrapSnippet();
                log("MCP token loaded — bridge authenticated", "ok");
                if (onDone) onDone(true);
            } else {
                reportMissingToken();
                if (onDone) onDone(false);
            }
        }).catch(function(e) {
            log("Could not read the MCP token: " + e, "err");
            if (onDone) onDone(false);
        });
    } catch(e) {
        log("Script Engine unavailable — cannot read the MCP token", "err");
        if (onDone) onDone(false);
    }
}

/* Without a token the bridge returns 401 for everything. Say WHERE it was
   searched, because the cause is almost always that the MCP server never ran
   on this machine. */
function reportMissingToken() {
    log("No MCP token found on this machine.", "err");
    log("Start the MCP server once (it creates the token on first run), " +
        "then reopen this window.", "warn");
    try {
        $se("getMcpTokenInfo").then(function(info) {
            var d = JSON.parse(info);
            (d.searched || []).forEach(function(p) { log("  looked in: " + p, "info"); });
        }).catch(function() {});
    } catch(e) {}
}

// ------------------------------------------------------------------ Init ---

function init() {
    // The token is read from disk through the Script Engine on every startup.
    // It is deliberately not cached with $putData: if the MCP server rotates it, the
    // cached copy would go stale and the failure would be invisible.
    loadToken();
    refreshBootstrapSnippet();
    applyShortcutLabels(IS_MAC);

    // Load persisted code
    try {
        $getData("code").then(function(code) {
            if (code) document.getElementById("codeeditor").value = code;
        }).catch(function() {});
    } catch(e) {}

    // Load history
    try {
        $getData("history").then(function(h) {
            if (h) {
                S.history = JSON.parse(h);
                refreshHistoryDropdown();
            }
        }).catch(function() {});
    } catch(e) {}

    log("PT-MCP Control Center started", "info");
    log("Polling bridge at http://127.0.0.1:54321 …", "info");

    // Update uptime every second
    setInterval(updateUptime, 1000);

    // Poll bridge every 2s
    setInterval(pollBridgeStatus, 2000);
    pollBridgeStatus();

    // Poll for commands every 500ms
    // Re-chains itself (long-poll); it has no setInterval.
    pollCommands();

    updateQBPreview();
}

// ------------------------------------------------------------------ Tabs ---

function switchTab(name) {
    S.activeTab = name;

    document.querySelectorAll(".tab-btn").forEach(function(b) {
        b.classList.toggle("active", b.id === "tab-" + name);
    });
    document.querySelectorAll(".pane").forEach(function(p) {
        p.classList.toggle("active", p.id === "pane-" + name);
    });

    // Show/hide editor toolbar
    var tb = document.getElementById("editor-toolbar");
    if (tb) tb.style.display = (name === "editor") ? "flex" : "none";

    // When switching to terminal, ensure log is rendered
    if (name === "terminal") renderLog();
}

// ---------------------------------------------------------------- Logging --

var TYPE_LABELS = {
    info: "INFO",
    ok:   " OK ",
    warn: "WARN",
    err:  " ERR",
    cmd:  " CMD",
    recv: "RECV",
};

function log(message, type) {
    type = type || "info";
    var now = new Date();
    var ts = now.toLocaleTimeString("en-GB", { hour12: false });

    S.logs.push({ ts: ts, type: type, msg: message });

    // Trim
    if (S.logs.length > S.maxLogs) S.logs.splice(0, S.logs.length - S.maxLogs);

    S.lastActivity = ts;
    setElText("st-last", ts);

    if (type === "err") {
        S.errCount++;
        var badge = document.getElementById("errBadge");
        if (badge) {
            badge.textContent = S.errCount > 99 ? "99+" : S.errCount;
            badge.classList.add("active");
            // Show notif if not on terminal tab
            if (S.activeTab !== "terminal") showNotif(message);
        }
    }

    // Only re-render if terminal is active (avoid heavy DOM work when hidden)
    if (S.activeTab === "terminal") {
        appendLogLine({ ts: ts, type: type, msg: message });
    }
}

function appendLogLine(entry) {
    // Filter check
    if (!logVisible(entry)) return;

    var search = document.getElementById("logSearch");
    var query = search ? search.value.trim().toLowerCase() : "";

    var panel = document.getElementById("logPanel");
    if (!panel) return;

    // Remove empty state
    var empty = panel.querySelector(".log-empty");
    if (empty) empty.remove();

    var line = document.createElement("div");
    line.className = "log-line " + entry.type;

    var msg = escapeHtml(entry.msg);
    if (query && msg.toLowerCase().indexOf(query) >= 0) {
        msg = msg.replace(new RegExp("(" + escapeRe(query) + ")", "gi"),
            '<span class="log-highlight">$1</span>');
    }

    line.innerHTML =
        '<span class="log-ts">' + entry.ts + '</span>' +
        '<span class="log-tag">' + (TYPE_LABELS[entry.type] || entry.type.toUpperCase()) + '</span>' +
        '<span class="log-msg">' + msg + '</span>';

    panel.appendChild(line);
    panel.scrollTop = panel.scrollHeight;

    updateLogCount();
}

function renderLog() {
    var panel = document.getElementById("logPanel");
    if (!panel) return;
    panel.innerHTML = "";

    var search = document.getElementById("logSearch");
    var query = search ? search.value.trim().toLowerCase() : "";

    var visible = S.logs.filter(logVisible);

    if (visible.length === 0) {
        panel.innerHTML =
            '<div class="log-empty">' +
            '<div class="log-empty-icon"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z"/></svg></div>' +
            '<div class="log-empty-text">No log entries match this filter</div>' +
            '</div>';
        updateLogCount(0);
        return;
    }

    visible.forEach(function(entry) {
        var line = document.createElement("div");
        line.className = "log-line " + entry.type;

        var msg = escapeHtml(entry.msg);
        if (query && msg.toLowerCase().indexOf(query) >= 0) {
            msg = msg.replace(new RegExp("(" + escapeRe(query) + ")", "gi"),
                '<span class="log-highlight">$1</span>');
        }

        line.innerHTML =
            '<span class="log-ts">' + entry.ts + '</span>' +
            '<span class="log-tag">' + (TYPE_LABELS[entry.type] || entry.type.toUpperCase()) + '</span>' +
            '<span class="log-msg">' + msg + '</span>';

        panel.appendChild(line);
    });

    panel.scrollTop = panel.scrollHeight;
    updateLogCount(visible.length);
}

function logVisible(entry) {
    var f = S.logFilter;
    if (f !== "all" && entry.type !== f) return false;
    var search = document.getElementById("logSearch");
    if (search && search.value.trim()) {
        return entry.msg.toLowerCase().indexOf(search.value.trim().toLowerCase()) >= 0;
    }
    return true;
}

function updateLogCount(n) {
    var el = document.getElementById("logCount");
    if (!el) return;
    var count = (n !== undefined) ? n : S.logs.filter(logVisible).length;
    el.textContent = count + " entr" + (count === 1 ? "y" : "ies");
}

function setFilter(f) {
    S.logFilter = f;
    document.querySelectorAll(".filter-btn").forEach(function(b) {
        b.classList.remove("active");
    });
    var btn = document.getElementById("f-" + f);
    if (btn) btn.classList.add("active");
    renderLog();
}

function clearLog() {
    S.logs = [];
    S.errCount = 0;
    var badge = document.getElementById("errBadge");
    if (badge) { badge.textContent = "0"; badge.classList.remove("active"); }
    renderLog();
    log("Log cleared", "info");
}

function exportLogs() {
    var lines = S.logs.map(function(e) {
        return "[" + e.ts + "] [" + (TYPE_LABELS[e.type] || e.type).trim() + "] " + e.msg;
    });
    navigator.clipboard.writeText(lines.join("\n")).then(function() {
        log("Exported " + lines.length + " log entries to clipboard", "ok");
    }).catch(function(e) {
        log("Export failed: " + e, "err");
    });
}

// ---------------------------------------------------------------- Bridge ---

function pollBridgeStatus() {
    try {
        var x = new XMLHttpRequest();
        x.open("GET", bridgeUrl("/status"), true);
        x.timeout = 2000;
        x.onload = function() {
            if (x.status === 401) {
                // The bridge is alive but does not recognize us: token missing,
                // expired or rotated. Retry the pairing once.
                handleUnauthorized();
                setBridgeDown();
                return;
            }
            if (x.status === 200) {
                try {
                    var data = JSON.parse(x.responseText);
                    var wasBridge = S.bridgeUp;
                    var wasPT = S.ptConnected;
                    S.bridgeUp = true;
                    S.ptConnected = data.connected;
                    S.lastPollAgo = data.last_poll_ago;

                    if (S.ptConnected) {
                        S.pollTimes.push(Date.now());
                        if (S.pollTimes.length > 20) S.pollTimes.shift();
                        renderSparkline();
                    }

                    if (!wasBridge)            log("Bridge HTTP online at :54321", "ok");
                    if (!wasPT && S.ptConnected) log("Packet Tracer connected — polling active", "ok");
                    if (wasPT && !S.ptConnected) log("PT disconnected — polling stopped", "warn");

                    updateConnectionUI();
                    // File channel status (runs in the Script Engine, with
                    // or without the window). It tells the user they can close the
                    // window and PT will keep executing commands.
                    try {
                        $se("fileBridgeStatus").then(function(s) {
                            try { S.fileBridge = JSON.parse(s); } catch(e) {}
                            updateFileBridgeBadge();
                        }).catch(function() {});
                    } catch(e) {}
                } catch(e) {
                    setBridgeDown();
                }
            } else {
                setBridgeDown();
            }
        };
        x.onerror = x.ontimeout = function() {
            if (S.bridgeUp) log("Bridge unreachable at :54321", "err");
            setBridgeDown();
        };
        x.send();
    } catch(e) {
        setBridgeDown();
    }
}

function setBridgeDown() {
    S.bridgeUp = false;
    S.ptConnected = false;
    updateConnectionUI();
}

/* Lights up the file-bridge badge when the Script Engine loop is alive.
   Green = PT keeps executing even when you close this window. */
function updateFileBridgeBadge() {
    var el = document.getElementById("fbBadge");
    if (!el) return;
    var fb = S.fileBridge;
    var label = "file-bridge";
    if (fb && fb.active) {
        el.className = "chip fb-badge ready";
        if (fb.count > 0) label += " · " + fb.count;
        el.title = "File-bridge active — PT keeps executing with this window closed"
                 + (fb.count > 0 ? " (" + fb.count + " commands run via file)" : "");
    } else {
        el.className = "chip fb-badge";
        el.title = "File-bridge inactive";
    }
    // preserve the leading dot span, replace only the label text
    el.innerHTML = '<span class="conn-dot"></span>' + label;
}

/* A 401 means the bridge is up but our token is not valid — typically
   because the server rotated it. It is re-read from disk, capped so it does
   not loop if the file is really missing. */
var _tokenReloads = 0;
function handleUnauthorized() {
    if (_tokenReloads >= 3) return;
    _tokenReloads++;
    log("Bridge rejected our token — re-reading it from disk…", "warn");
    loadToken(function(ok) {
        if (ok) _tokenReloads = 0;
    });
}

/* Chained long-poll: the bridge holds /next until there is something (or ~2s) and
   returns ALL queued commands at once. This used to be a setInterval of 500 ms
   that fetched one command per round trip, so a 40-command topology took tens
   of seconds. It always re-chains — there is never a branch that leaves the
   loop dead. */
function pollCommands() {
    if (!S.bridgeUp) { setTimeout(pollCommands, 500); return; }
    var again = function() { setTimeout(pollCommands, 0); };
    try {
        var x = new XMLHttpRequest();
        x.open("GET", bridgeUrl("/next"), true);
        // Looser than the bridge's long-poll, so we do not cut it off ourselves.
        x.timeout = 8000;
        x.onload = function() {
            if (x.status === 401) { handleUnauthorized(); setTimeout(pollCommands, 1000); return; }
            if (x.status === 200 && x.responseText) {
                var batch = x.responseText;
                var n = batch.split("\n").length;
                var preview = batch.length > 120 ? batch.substring(0, 120) + "…" : batch;
                log("MCP → PT (" + n + " cmd" + (n > 1 ? "s" : "") + "): " + preview, "recv");
                try {
                    // The whole batch goes in a single runCode: each command already
                    // carries its own try/catch, so one bad one does not take down the others.
                    $se("runCode", batch);
                    S.commandCount += n;
                    log("Batch executed", "ok");
                    updateCommandCount();
                } catch(e) {
                    log("Execution failed: " + e.message, "err");
                }
            }
            again();
        };
        x.onerror = x.ontimeout = function() { setTimeout(pollCommands, 500); };
        x.send();
    } catch(e) {
        setTimeout(pollCommands, 1000);
    }
}

function updateConnectionUI() {
    // Header dot + label
    var dot   = document.getElementById("connDot");
    var label = document.getElementById("connLabel");
    var sbDot = document.getElementById("sb-bridge-dot");
    var sbLbl = document.getElementById("sb-bridge-label");
    var httpChip  = document.getElementById("httpChip");
    var tokenChip = document.getElementById("tokenChip");

    var timelineFill = document.getElementById("timelineFill");

    // Token chip: if we ever polled successfully, the token is working.
    if (tokenChip) tokenChip.className = S.bridgeUp ? "chip on" : "chip";

    if (S.ptConnected) {
        if (httpChip) httpChip.className = "chip on";
        if (dot)   { dot.className = "conn-dot connected"; }
        if (label) { label.textContent = "HTTP"; }
        if (sbDot) sbDot.className = "status-bar-dot ok";
        if (sbLbl) sbLbl.textContent = "Bridge: connected";
        if (timelineFill) timelineFill.style.width = "100%";

        setElText("st-bridge", "UP :54321");
        setElClass("st-bridge", "stat-value ok");
        setCardClass("card-bridge", "stat-card ok");

        setElText("st-pt", "Connected");
        setElClass("st-pt", "stat-value ok");
        setCardClass("card-pt", "stat-card ok");
        setElText("st-poll-sub", "polling every 500ms");

    } else if (S.bridgeUp) {
        if (httpChip) httpChip.className = "chip warn";
        if (dot)   { dot.className = "conn-dot bridge-only"; }
        if (label) { label.textContent = "waiting"; }
        if (sbDot) sbDot.className = "status-bar-dot warn";
        if (sbLbl) sbLbl.textContent = "Bridge: up, PT offline";
        if (timelineFill) timelineFill.style.width = "50%";

        setElText("st-bridge", "UP :54321");
        setElClass("st-bridge", "stat-value ok");
        setCardClass("card-bridge", "stat-card ok");

        setElText("st-pt", "Waiting…");
        setElClass("st-pt", "stat-value warn");
        setCardClass("card-pt", "stat-card warn");
        setElText("st-poll-sub", "PT not polling");

    } else {
        if (httpChip) httpChip.className = "chip";
        if (dot)   { dot.className = "conn-dot"; }
        if (label) { label.textContent = "offline"; }
        if (sbDot) sbDot.className = "status-bar-dot err";
        if (sbLbl) sbLbl.textContent = "Bridge: offline";
        if (timelineFill) timelineFill.style.width = "0%";

        setElText("st-bridge", "DOWN");
        setElClass("st-bridge", "stat-value err");
        setCardClass("card-bridge", "stat-card err");

        setElText("st-pt", "Offline");
        setElClass("st-pt", "stat-value err");
        setCardClass("card-pt", "stat-card err");
        setElText("st-poll-sub", "not polling");
    }

    updateCommandCount();
}

function updateCommandCount() {
    setElText("st-cmds", S.commandCount);
    setElText("sb-cmds", S.commandCount + " cmd" + (S.commandCount !== 1 ? "s" : ""));
}

// ---------------------------------------------------------------- Sparkline --

function renderSparkline() {
    var svg = document.getElementById("sparkline");
    if (!svg) return;

    var W = 200, H = 36;
    var times = S.pollTimes;
    if (times.length < 2) { svg.innerHTML = ""; return; }

    var min = times[0], max = times[times.length - 1];
    var range = max - min || 1;

    var bars = times.map(function(t, i) {
        var x = Math.round(((t - min) / range) * (W - 8));
        var h = 8 + (i / times.length) * 20;
        var y = H - h;
        return '<rect x="' + x + '" y="' + y + '" width="6" height="' + h +
            '" rx="2" fill="#4f8ef7" opacity="' + (0.3 + 0.7 * i / times.length) + '"/>';
    });

    svg.innerHTML = bars.join("");
}

// ------------------------------------------------------------------ Uptime --

function updateUptime() {
    var elapsed = Math.floor((Date.now() - S.sessionStart) / 1000);
    var m = Math.floor(elapsed / 60);
    var s = elapsed % 60;
    var str = pad2(m) + ":" + pad2(s);
    setElText("st-uptime", str);
    setElText("sb-uptime", str);
}

// --------------------------------------------------------------- Editor ----

function onEditorInput() {
    var indicator = document.getElementById("saveIndicator");
    if (indicator) { indicator.textContent = "● saving…"; indicator.className = "save-indicator"; }
    if (S._saveTimer) clearTimeout(S._saveTimer);
    S._saveTimer = setTimeout(function() {
        saveCode();
        if (indicator) { indicator.textContent = "● saved"; indicator.className = "save-indicator saved"; }
    }, 800);
    S.historyPos = -1; // reset navigator on manual edit
}

function saveCode() {
    var code = document.getElementById("codeeditor").value;
    try { $putData("code", code); } catch(e) {}
}

function loadCode() {
    try {
        $getData("code").then(function(code) {
            document.getElementById("codeeditor").value = code || "";
        }).catch(function() {});
    } catch(e) {}
}

function executeCode() {
    var code = document.getElementById("codeeditor").value;
    if (!code.trim()) {
        log("Editor is empty — nothing to execute", "warn");
        return;
    }

    if (!S.bridgeUp) {
        log("Bridge is offline — cannot execute. Start the bridge first.", "warn");
        showNotif("Bridge is offline. Start the MCP server and paste the bootstrap snippet.");
        switchTab("status");
        return;
    }

    // Push to history
    if (!S.history.length || S.history[S.history.length - 1] !== code) {
        S.history.push(code);
        if (S.history.length > 20) S.history.shift();
        persistHistory();
        refreshHistoryDropdown();
    }
    S.historyPos = -1;

    var preview = code.trim().substring(0, 100);
    log("Executing: " + preview + (code.length > 100 ? " …" : ""), "cmd");

    // Split into individual commands and send through bridge (same pipeline as Quick Build)
    var lines = code.split("\n").filter(function(l) {
        var t = l.trim();
        return t && !t.startsWith("//");
    });

    var cmds = lines.map(function(line) {
        var cmd = line.trim();
        // Add semicolon if missing (PT Script Engine requires it)
        return cmd.endsWith(";") ? cmd : cmd + ";";
    });

    queueCommands(cmds, function(sent) {
        if (sent > 0) {
            S.commandCount += sent;
            updateCommandCount();
            log(sent + " command" + (sent > 1 ? "s" : "") + " queued via bridge", "ok");
        } else {
            log("Failed to queue commands — check bridge connection", "err");
        }
        switchTab("terminal");
    });
}

/* Queues a batch in a single ASYNCHRONOUS request.
   It used to be a synchronous XHR per command inside a forEach: it blocked the
   webview UI thread and made one HTTP round trip per line. */
function queueCommands(cmds, onDone) {
    if (!cmds || !cmds.length) { if (onDone) onDone(0); return; }
    try {
        var x = new XMLHttpRequest();
        x.open("POST", bridgeUrl("/queue"), true);
        x.setRequestHeader("Content-Type", "text/plain");
        x.timeout = 5000;
        x.onload = function() {
            if (x.status === 401) { handleUnauthorized(); if (onDone) onDone(0); return; }
            if (onDone) onDone(x.status === 200 ? cmds.length : 0);
        };
        x.onerror = x.ontimeout = function() { if (onDone) onDone(0); };
        x.send(cmds.join("\n"));
    } catch(e) {
        if (onDone) onDone(0);
    }
}

function clearEditor() {
    var editor = document.getElementById("codeeditor");
    if (!editor.value.trim()) return;
    editor.value = "";
    log("Editor cleared", "info");
    S.historyPos = -1;
    try { $putData("code", ""); } catch(e) {}
}

function copyToClipboard() {
    var code = document.getElementById("codeeditor").value;
    navigator.clipboard.writeText(code).then(function() {
        log("Copied to clipboard (" + code.length + " chars)", "ok");
    }).catch(function(e) {
        log("Clipboard write failed: " + e, "err");
    });
}

function pasteFromClipboard() {
    navigator.clipboard.readText().then(function(text) {
        document.getElementById("codeeditor").value = text;
        log("Pasted from clipboard (" + text.length + " chars)", "ok");
        onEditorInput();
    }).catch(function(e) {
        log("Clipboard read failed: " + e, "err");
    });
}

// ----------------------------------------------------------- History -------

function persistHistory() {
    try { $putData("history", JSON.stringify(S.history)); } catch(e) {}
}

function refreshHistoryDropdown() {
    var sel = document.getElementById("historySelect");
    if (!sel) return;
    sel.innerHTML = '<option value="">— History (' + S.history.length + ') —</option>';
    for (var i = S.history.length - 1; i >= 0; i--) {
        var preview = S.history[i].trim().replace(/\n/g, " ").substring(0, 60);
        var opt = document.createElement("option");
        opt.value = i;
        opt.textContent = (S.history.length - i) + ". " + preview;
        sel.appendChild(opt);
    }
}

function loadFromHistory(idx) {
    if (idx === "" || idx === null) return;
    var code = S.history[parseInt(idx, 10)];
    if (code !== undefined) {
        document.getElementById("codeeditor").value = code;
        log("Loaded from history #" + (parseInt(idx, 10) + 1), "info");
    }
    document.getElementById("historySelect").value = "";
}

// -------------------------------------------------- Keyboard shortcuts -----

// Shortcuts use the OS's own modifier: Command on macOS, Ctrl elsewhere. On a
// Mac, Control+K is the text system's "delete to end of line" and Control+L
// centres the caret line, so the editor must not take them over there.
var SHORTCUTS = {
    run:      { key: "enter", mac: "⌘↩", other: "Ctrl+Enter" },
    clear:    { key: "k",     mac: "⌘K",      other: "Ctrl+K" },
    clearLog: { key: "l",     mac: "⌘L",      other: "Ctrl+L" },
};

function isMacPlatform(platform, userAgent) {
    return /Mac|iPhone|iPad|iPod/i.test(platform || "")
        || /Macintosh|Mac OS X/i.test(userAgent || "");
}

var IS_MAC = isMacPlatform(navigator.platform, navigator.userAgent);

// True when e is the named shortcut on this OS: the OS's modifier held, and no
// other modifier (so Ctrl+Cmd+K or Shift+Ctrl+K stay free for the system).
function isShortcut(e, name, mac) {
    var primary = mac ? e.metaKey : e.ctrlKey;
    var other = mac ? e.ctrlKey : e.metaKey;
    return !!primary && !other && !e.altKey && !e.shiftKey
        && String(e.key).toLowerCase() === SHORTCUTS[name].key;
}

function shortcutLabel(name, mac) {
    return mac ? SHORTCUTS[name].mac : SHORTCUTS[name].other;
}

// Rewrites the hints in index.html for this OS: data-shortcut="<name>" sets the
// element's text, data-shortcut-title="<name>" its tooltip ("<data-title> (<key>)").
// The HTML keeps the Windows text as a fallback if this never runs.
function applyShortcutLabels(mac) {
    var labels = document.querySelectorAll("[data-shortcut]");
    for (var i = 0; i < labels.length; i++) {
        labels[i].textContent = shortcutLabel(labels[i].getAttribute("data-shortcut"), mac);
    }
    var titled = document.querySelectorAll("[data-shortcut-title]");
    for (var j = 0; j < titled.length; j++) {
        var el = titled[j];
        el.title = el.getAttribute("data-title") + " ("
            + shortcutLabel(el.getAttribute("data-shortcut-title"), mac) + ")";
    }
}

function editorKeyDown(e) {
    var editor = document.getElementById("codeeditor");

    // Cmd+Return (macOS) / Ctrl+Enter → Run
    if (isShortcut(e, "run", IS_MAC)) {
        e.preventDefault();
        executeCode();
        return;
    }

    // Cmd+K (macOS) / Ctrl+K → Clear editor
    if (isShortcut(e, "clear", IS_MAC)) {
        e.preventDefault();
        clearEditor();
        return;
    }

    // Arrow Up at start of textarea → history back
    if (e.key === "ArrowUp" && editor.selectionStart === 0 && S.history.length > 0) {
        if (S.historyPos < S.history.length - 1) {
            S.historyPos++;
            editor.value = S.history[S.history.length - 1 - S.historyPos];
        }
        e.preventDefault();
        return;
    }

    // Arrow Down → history forward
    if (e.key === "ArrowDown" && editor.selectionEnd === editor.value.length && S.historyPos >= 0) {
        S.historyPos--;
        if (S.historyPos < 0) {
            editor.value = "";
        } else {
            editor.value = S.history[S.history.length - 1 - S.historyPos];
        }
        e.preventDefault();
        return;
    }
}

// Global keyboard shortcut — Cmd+L (macOS) / Ctrl+L to clear log from any tab
document.addEventListener("keydown", function(e) {
    if (isShortcut(e, "clearLog", IS_MAC)) {
        e.preventDefault();
        clearLog();
    }
});

// -------------------------------------------------------- Bootstrap snippet -

function copyBootstrap() {
    navigator.clipboard.writeText(bootstrapSnippet()).then(function() {
        log("Bootstrap snippet copied to clipboard", "ok");
    }).catch(function(e) {
        log("Failed to copy: " + e, "err");
    });
}

// ---------------------------------------------------------- Quick Build ----

function getQBValues() {
    return {
        template:      val("qb-template"),
        routing:       val("qb-routing"),
        routerModel:   val("qb-router-model"),
        switchModel:   val("qb-switch-model"),
        routers:       intVal("qb-routers"),
        pcs:           intVal("qb-pcs"),
        switches:      intVal("qb-switches"),
        servers:       intVal("qb-servers"),
        dhcp:          checked("qb-dhcp"),
        wan:           checked("qb-wan"),
        floating:      checked("qb-floating"),
    };
}

function updateQBPreview() {
    var v = getQBValues();
    var parts = [
        v.template, v.routing,
        v.routers + "R", v.pcs + "PC", v.switches + "SW",
        v.servers > 0 ? v.servers + "SRV" : null,
        v.dhcp ? "DHCP" : null,
        v.wan ? "WAN" : null,
    ].filter(Boolean);
    setElText("qbPreview", parts.join(" · "));
}

function buildQBScript(v) {
    // Generates addDevice + addLink commands matching the PT Builder API:
    //   addDevice(name, model, x, y);
    //   addLink(devA, portA, devB, portB, cableType);
    // Cable types: "cross" for router↔router, "straight" for everything else.

    var lines = [];
    var spacing = 250;
    var routerY = 200;

    // Helper: router port name (ISR4321/4331 uses triple index)
    function rPort(idx) {
        if (v.routerModel === "ISR4321" || v.routerModel === "ISR4331") {
            return "GigabitEthernet0/0/" + idx;
        }
        return "GigabitEthernet0/" + idx;
    }

    // Determine effective router count based on template
    var numRouters = v.routers;
    if (v.template === "single_lan") numRouters = 1;
    if (v.template === "three_router_triangle") numRouters = 3;

    lines.push("// Quick Build: " + v.template + " | " + numRouters + "x " + v.routerModel +
        " | " + v.pcs + " PC/LAN | " + v.routing);

    // ── ROUTER POSITIONS (depend on template) ────────────────────────
    var rPos = []; // { name, x, y }

    if (v.template === "star" || v.template === "hub_spoke") {
        // Central hub + spokes in a circle
        var cx = 400, cy = 250;
        rPos.push({ name: "R1", x: cx, y: cy });
        var rad = 220;
        for (var i = 1; i < numRouters; i++) {
            var angle = (2 * Math.PI * (i - 1)) / Math.max(numRouters - 1, 1) - Math.PI / 2;
            rPos.push({
                name: "R" + (i + 1),
                x: Math.round(cx + rad * Math.cos(angle)),
                y: Math.round(cy + rad * Math.sin(angle))
            });
        }
    } else if (v.template === "three_router_triangle") {
        rPos = [
            { name: "R1", x: 300, y: 100 },
            { name: "R2", x: 100, y: 350 },
            { name: "R3", x: 500, y: 350 }
        ];
    } else {
        // Linear chain: single_lan, multi_lan, multi_lan_wan, branch_office, router_on_a_stick
        for (var r = 0; r < numRouters; r++) {
            rPos.push({ name: "R" + (r + 1), x: 100 + r * spacing, y: routerY });
        }
    }

    // ── ADD DEVICES ──────────────────────────────────────────────────
    lines.push("// Devices");

    rPos.forEach(function(rp) {
        lines.push('addDevice("' + rp.name + '", "' + v.routerModel + '", ' + rp.x + ', ' + rp.y + ');');
    });

    rPos.forEach(function(rp, idx) {
        var swYPos = rp.y + 150;
        for (var sw = 0; sw < v.switches; sw++) {
            var swName = "SW" + (idx + 1) + (v.switches > 1 ? String.fromCharCode(65 + sw) : "");
            lines.push('addDevice("' + swName + '", "' + v.switchModel + '", ' + (rp.x + sw * 80) + ', ' + swYPos + ');');
        }
        for (var p = 0; p < v.pcs; p++) {
            var pcName = "PC" + (idx + 1) + "-" + (p + 1);
            var pcX = rp.x - Math.floor(v.pcs / 2) * 60 + p * 60;
            lines.push('addDevice("' + pcName + '", "PC-PT", ' + pcX + ', ' + (rp.y + 300) + ');');
        }
    });

    if (v.servers > 0) {
        for (var s = 0; s < v.servers; s++) {
            lines.push('addDevice("SRV' + (s + 1) + '", "Server-PT", ' + (100 + s * 80) + ', ' + (routerY + 430) + ');');
        }
    }

    if (v.wan && v.template === "multi_lan_wan") {
        var cloudX = 100 + Math.floor(numRouters / 2) * spacing;
        lines.push('addDevice("Cloud1", "Cloud-PT", ' + cloudX + ', ' + (routerY - 150) + ');');
    }

    // ── ADD LINKS ─────────────────────────────────────────────────────
    lines.push("// Links");

    // --- Router ↔ Router links ---
    if (v.template === "star" || v.template === "hub_spoke") {
        // Hub (R1) connects to each spoke via consecutive GE ports
        for (var si = 1; si < numRouters; si++) {
            lines.push('addLink("R1", "' + rPort(si - 1) + '", "R' + (si + 1) + '", "' + rPort(0) + '", "cross");');
        }
    } else if (v.template === "three_router_triangle") {
        // Triangle: R1↔R2, R2↔R3, R3↔R1  (each router uses GE0/0 and GE0/1 for WAN)
        lines.push('addLink("R1", "' + rPort(0) + '", "R2", "' + rPort(0) + '", "cross");');
        lines.push('addLink("R2", "' + rPort(1) + '", "R3", "' + rPort(0) + '", "cross");');
        lines.push('addLink("R3", "' + rPort(1) + '", "R1", "' + rPort(1) + '", "cross");');
    } else {
        // Linear chain: R[i] → R[i+1]
        // Port scheme matching real topology output:
        //   R1 (edge):   GE0/0 = WAN right,      GE0/1 = LAN
        //   Middle:      GE0/0 = WAN left,        GE0/1 = WAN right,  GE0/2 = LAN
        //   R_last (edge): GE0/0 = WAN left,      GE0/1 = LAN
        for (var ri = 0; ri < numRouters - 1; ri++) {
            var fromR = "R" + (ri + 1);
            var toR   = "R" + (ri + 2);
            var fromPort = (ri === 0) ? rPort(0) : rPort(1); // edge uses 0, middle uses 1 (right exit)
            var toPort   = rPort(0);                          // always arrives on 0
            lines.push('addLink("' + fromR + '", "' + fromPort + '", "' + toR + '", "' + toPort + '", "cross");');
        }
    }

    // --- Router → Switch LAN links ---
    if (v.switches > 0) {
        rPos.forEach(function(rp, idx) {
            var rName  = rp.name;
            var swName = "SW" + (idx + 1) + (v.switches > 1 ? "A" : "");
            var lanIdx;

            if (v.template === "star" || v.template === "hub_spoke") {
                if (idx === 0) {
                    lanIdx = numRouters - 1; // Hub: LAN port after all WAN ports
                } else {
                    lanIdx = 1;              // Spoke: GE0/0=WAN, GE0/1=LAN
                }
            } else if (v.template === "three_router_triangle") {
                lanIdx = 2; // GE0/0 & GE0/1 are WAN, GE0/2 = LAN
            } else {
                // Linear chain
                if (numRouters === 1) {
                    lanIdx = 0; // Single router: GE0/0 = LAN
                } else if (idx === 0 || idx === numRouters - 1) {
                    lanIdx = 1; // Edge: GE0/0=WAN, GE0/1=LAN
                } else {
                    lanIdx = 2; // Middle: GE0/0=WAN left, GE0/1=WAN right, GE0/2=LAN
                }
            }

            lines.push('addLink("' + rName + '", "' + rPort(lanIdx) + '", "' + swName + '", "GigabitEthernet0/1", "straight");');
        });
    }

    // --- Switch → PCs ---
    if (v.switches > 0 && v.pcs > 0) {
        rPos.forEach(function(rp, idx) {
            var swName = "SW" + (idx + 1) + (v.switches > 1 ? "A" : "");
            for (var p = 0; p < v.pcs; p++) {
                var pcName = "PC" + (idx + 1) + "-" + (p + 1);
                var swPort = "FastEthernet0/" + (p + 1);
                lines.push('addLink("' + swName + '", "' + swPort + '", "' + pcName + '", "FastEthernet0", "straight");');
            }
        });
    }

    // --- Switch → Servers ---
    if (v.servers > 0 && v.switches > 0) {
        var srvSw = "SW1" + (v.switches > 1 ? "A" : "");
        for (var s2 = 0; s2 < v.servers; s2++) {
            var srvSwPort = "FastEthernet0/" + (v.pcs + 1 + s2);
            lines.push('addLink("' + srvSw + '", "' + srvSwPort + '", "SRV' + (s2 + 1) + '", "FastEthernet0", "straight");');
        }
    }

    // --- WAN Cloud link ---
    if (v.wan && v.template === "multi_lan_wan") {
        // Connect Cloud to R1 on next available GE port
        var cloudPort = (numRouters === 1) ? 1 : 2;
        lines.push('addLink("R1", "' + rPort(cloudPort) + '", "Cloud1", "Ethernet0", "straight");');
    }

    // ── IOS CONFIGURATIONS ────────────────────────────────────────────
    lines.push("// IOS Configurations");

    // Build WAN link map: for each router, which port connects to which router, and what IPs
    // Inter-router links use 10.0.{linkIdx}.0/30 — .1 for left/hub side, .2 for right/spoke side
    // LAN subnets use 192.168.{routerIdx}.0/24 — gateway .1, PCs from .2
    var wanLinks = []; // { fromR, toR, fromPort, toPort, subnet: linkIdx }

    if (v.template === "star" || v.template === "hub_spoke") {
        for (var wi = 1; wi < numRouters; wi++) {
            wanLinks.push({
                fromR: "R1", toR: "R" + (wi + 1),
                fromPort: rPort(wi - 1), toPort: rPort(0),
                linkIdx: wi - 1
            });
        }
    } else if (v.template === "three_router_triangle") {
        wanLinks.push({ fromR: "R1", toR: "R2", fromPort: rPort(0), toPort: rPort(0), linkIdx: 0 });
        wanLinks.push({ fromR: "R2", toR: "R3", fromPort: rPort(1), toPort: rPort(0), linkIdx: 1 });
        wanLinks.push({ fromR: "R3", toR: "R1", fromPort: rPort(1), toPort: rPort(1), linkIdx: 2 });
    } else {
        for (var wri = 0; wri < numRouters - 1; wri++) {
            wanLinks.push({
                fromR: "R" + (wri + 1), toR: "R" + (wri + 2),
                fromPort: (wri === 0) ? rPort(0) : rPort(1),
                toPort: rPort(0),
                linkIdx: wri
            });
        }
    }

    // Compute LAN port index for each router (same logic as links section)
    function getLanIdx(idx) {
        if (v.template === "star" || v.template === "hub_spoke") {
            return (idx === 0) ? numRouters - 1 : 1;
        } else if (v.template === "three_router_triangle") {
            return 2;
        } else {
            if (numRouters === 1) return 0;
            if (idx === 0 || idx === numRouters - 1) return 1;
            return 2;
        }
    }

    // Generate configureIosDevice for each router
    rPos.forEach(function(rp, idx) {
        var cfg = [];
        cfg.push("enable");
        cfg.push("configure terminal");
        cfg.push("hostname " + rp.name);
        cfg.push("no ip domain-lookup");
        cfg.push("");

        // WAN interfaces
        wanLinks.forEach(function(wl) {
            if (wl.fromR === rp.name) {
                var ip = "10.0." + wl.linkIdx + ".1";
                cfg.push("interface " + wl.fromPort);
                cfg.push(" ip address " + ip + " 255.255.255.252");
                cfg.push(" no shutdown");
                cfg.push(" exit");
                cfg.push("");
            }
            if (wl.toR === rp.name) {
                var ip2 = "10.0." + wl.linkIdx + ".2";
                cfg.push("interface " + wl.toPort);
                cfg.push(" ip address " + ip2 + " 255.255.255.252");
                cfg.push(" no shutdown");
                cfg.push(" exit");
                cfg.push("");
            }
        });

        // LAN interface
        if (v.switches > 0 || v.pcs > 0) {
            var lanPort = rPort(getLanIdx(idx));
            var lanNet = "192.168." + idx + ".1";
            cfg.push("interface " + lanPort);
            cfg.push(" ip address " + lanNet + " 255.255.255.0");
            cfg.push(" no shutdown");
            cfg.push(" exit");
            cfg.push("");
        }

        // DHCP pool
        if (v.dhcp && (v.switches > 0 || v.pcs > 0)) {
            cfg.push("ip dhcp excluded-address 192.168." + idx + ".1 192.168." + idx + ".1");
            cfg.push("ip dhcp pool LAN_" + rp.name);
            cfg.push(" network 192.168." + idx + ".0 255.255.255.0");
            cfg.push(" default-router 192.168." + idx + ".1");
            cfg.push(" dns-server 8.8.8.8");
            cfg.push(" exit");
            cfg.push("");
        }

        // Routing
        if (v.routing === "static") {
            // Static routes to all other LAN subnets
            rPos.forEach(function(otherRp, otherIdx) {
                if (otherIdx === idx) return;
                // Find next-hop: the WAN peer IP toward destination
                var nextHop = findNextHop(rp.name, otherIdx, wanLinks, rPos, numRouters, v.template);
                if (nextHop) {
                    cfg.push("ip route 192.168." + otherIdx + ".0 255.255.255.0 " + nextHop);
                }
            });
            cfg.push("");
        } else if (v.routing === "ospf") {
            cfg.push("router ospf 1");
            cfg.push(" router-id " + (idx + 1) + "." + (idx + 1) + "." + (idx + 1) + "." + (idx + 1));
            // Advertise LAN
            if (v.switches > 0 || v.pcs > 0) {
                cfg.push(" network 192.168." + idx + ".0 0.0.0.255 area 0");
            }
            // Advertise WAN links
            wanLinks.forEach(function(wl) {
                if (wl.fromR === rp.name || wl.toR === rp.name) {
                    cfg.push(" network 10.0." + wl.linkIdx + ".0 0.0.0.3 area 0");
                }
            });
            cfg.push(" exit");
            cfg.push("");
        } else if (v.routing === "eigrp") {
            cfg.push("router eigrp 100");
            if (v.switches > 0 || v.pcs > 0) {
                cfg.push(" network 192.168." + idx + ".0 0.0.0.255");
            }
            wanLinks.forEach(function(wl) {
                if (wl.fromR === rp.name || wl.toR === rp.name) {
                    cfg.push(" network 10.0." + wl.linkIdx + ".0 0.0.0.3");
                }
            });
            cfg.push(" no auto-summary");
            cfg.push(" exit");
            cfg.push("");
        } else if (v.routing === "rip") {
            cfg.push("router rip");
            cfg.push(" version 2");
            if (v.switches > 0 || v.pcs > 0) {
                cfg.push(" network 192.168." + idx + ".0");
            }
            wanLinks.forEach(function(wl) {
                if (wl.fromR === rp.name || wl.toR === rp.name) {
                    cfg.push(" network 10.0." + wl.linkIdx + ".0");
                }
            });
            cfg.push(" no auto-summary");
            cfg.push(" exit");
            cfg.push("");
        }

        cfg.push("end");
        cfg.push("write memory");

        // Escape for JS string: replace \ with \\ then " with \"  then newlines with \n
        var cfgStr = cfg.join("\\n");
        lines.push('configureIosDevice("' + rp.name + '", "' + cfgStr + '");');
    });

    // Generate switch hostname config
    rPos.forEach(function(rp, idx) {
        for (var sw = 0; sw < v.switches; sw++) {
            var swName = "SW" + (idx + 1) + (v.switches > 1 ? String.fromCharCode(65 + sw) : "");
            var swCfg = "enable\\nhostname " + swName + "\\nend\\nwrite memory";
            lines.push('configureIosDevice("' + swName + '", "' + swCfg + '");');
        }
    });

    // Configure PCs
    lines.push("// PC IP Configuration");
    rPos.forEach(function(rp, idx) {
        for (var p = 0; p < v.pcs; p++) {
            var pcName = "PC" + (idx + 1) + "-" + (p + 1);
            if (v.dhcp) {
                lines.push('configurePcIp("' + pcName + '", true);');
            } else {
                var pcIp   = "192.168." + idx + "." + (p + 2);
                var pcMask = "255.255.255.0";
                var pcGw   = "192.168." + idx + ".1";
                lines.push('configurePcIp("' + pcName + '", false, "' + pcIp + '", "' + pcMask + '", "' + pcGw + '");');
            }
        }
    });

    // Configure Servers
    if (v.servers > 0) {
        for (var sv = 0; sv < v.servers; sv++) {
            var srvName = "SRV" + (sv + 1);
            if (v.dhcp) {
                lines.push('configurePcIp("' + srvName + '", true);');
            } else {
                var srvIp = "192.168.0." + (v.pcs + 2 + sv);
                lines.push('configurePcIp("' + srvName + '", false, "' + srvIp + '", "255.255.255.0", "192.168.0.1");');
            }
        }
    }

    return lines.join("\n");
}

// Helper: find next-hop IP for static routing (simple: direct neighbor or via first hop)
function findNextHop(fromName, destIdx, wanLinks, rPos, numRouters, template) {
    // For star/hub_spoke: hub knows all spokes directly, spokes go through hub
    if (template === "star" || template === "hub_spoke") {
        if (fromName === "R1") {
            // Hub to spoke: direct link
            for (var i = 0; i < wanLinks.length; i++) {
                if (wanLinks[i].toR === rPos[destIdx].name) {
                    return "10.0." + wanLinks[i].linkIdx + ".2";
                }
            }
        } else {
            // Spoke to anywhere: go through hub (R1)
            for (var j = 0; j < wanLinks.length; j++) {
                if (wanLinks[j].toR === fromName) {
                    return "10.0." + wanLinks[j].linkIdx + ".1";
                }
            }
        }
        return null;
    }

    // For triangle: find direct link to dest, or route through first available neighbor
    if (template === "three_router_triangle") {
        var destName = rPos[destIdx].name;
        // Direct link?
        for (var t = 0; t < wanLinks.length; t++) {
            if (wanLinks[t].fromR === fromName && wanLinks[t].toR === destName) {
                return "10.0." + wanLinks[t].linkIdx + ".2";
            }
            if (wanLinks[t].toR === fromName && wanLinks[t].fromR === destName) {
                return "10.0." + wanLinks[t].linkIdx + ".1";
            }
        }
        // Not directly connected — go via first neighbor
        for (var u = 0; u < wanLinks.length; u++) {
            if (wanLinks[u].fromR === fromName) return "10.0." + wanLinks[u].linkIdx + ".2";
            if (wanLinks[u].toR === fromName) return "10.0." + wanLinks[u].linkIdx + ".1";
        }
        return null;
    }

    // Linear chain: find direction toward destination
    var fromIdx = -1;
    for (var fi = 0; fi < rPos.length; fi++) {
        if (rPos[fi].name === fromName) { fromIdx = fi; break; }
    }
    if (fromIdx < 0) return null;

    if (destIdx > fromIdx) {
        // Go right: use link fromIdx → fromIdx+1
        for (var r = 0; r < wanLinks.length; r++) {
            if (wanLinks[r].fromR === fromName) return "10.0." + wanLinks[r].linkIdx + ".2";
        }
        // Might be the "toR" side
        for (var r2 = 0; r2 < wanLinks.length; r2++) {
            if (wanLinks[r2].toR === rPos[fromIdx + 1].name && wanLinks[r2].fromR === fromName) {
                return "10.0." + wanLinks[r2].linkIdx + ".2";
            }
        }
    } else {
        // Go left: use link fromIdx-1 → fromIdx, next-hop is .1
        for (var l = 0; l < wanLinks.length; l++) {
            if (wanLinks[l].toR === fromName) return "10.0." + wanLinks[l].linkIdx + ".1";
        }
    }
    return null;
}

function quickBuild() {
    var v = getQBValues();

    if (!S.ptConnected) {
        log("PT not connected — check Status tab and paste the bootstrap snippet first", "warn");
        showNotif("PT is not connected. Paste the bootstrap snippet in PT first.");
        switchTab("status");
        return;
    }

    var script = buildQBScript(v);
    log("Quick Build: sending " + v.routers + "R " + v.pcs + "PC topology via bridge…", "cmd");

    var lines = script.split("\n").filter(function(l) { return l.trim() && !l.trim().startsWith("//"); });

    queueCommands(lines, function(sent) {
        if (sent > 0) {
            S.commandCount += sent;
            updateCommandCount();
            log("Quick Build: " + sent + " commands queued", "ok");
            switchTab("terminal");
        } else {
            log("Quick Build: failed to queue commands (bridge error)", "err");
        }
    });
}

// ---------------------------------------------------- Simulation demos -----
/* Ready-made Simulation demos for a LAN behind a remote server (local build,
   not committed). The helpers below run in PT's Script Engine: runCode installs
   them on GLOBAL, then $se calls them by name and gets their JSON back. Play is
   always paused again: by the tick once every PDU ended, or after SIM_MAX_MS
   (a Play left running fills PT's event buffer: "maximum number of events"). */
var SIM_MAX_MS = { broadcast: 180000, pc2pc: 120000, srv2pc: 120000, srv2all: 150000 };  // per batch
var SIM_BATCH = 10;
var SIM_TICK_MS = 1000;
var SIM = { running: false, timer: null, t0: 0, label: "" };

function simEngineHelpers() {
    var G = GLOBAL;
    function J(o){ return JSON.stringify(o); }
    function S(){ return ipc.simulation(); }
    function P(){ return ipc.appWindow().getSimulationPanel(); }
    function U(){ return ipc.appWindow().getUserCreatedPDU(); }
    function winSim(){ try { return !!ipc.appWindow().isSimulationMode(); } catch(e){ return null; } }
    function pause(){ try { if (P().isPlaying()) { P().play(); } } catch(e){} }
    // Deleting a user PDU also drops its frames from the buffer (live, 388 -> 0).
    function clearPdus(){ for (var i = 0; i < 500; i++) { try { U().deletePDU(0); } catch(e){ break; } } }
    function hostIp(d){
        var names = ["FastEthernet0", "GigabitEthernet0", "Wireless0"];
        for (var i = 0; i < names.length; i++) {
            try { var p = d.getPort(names[i]); if (p && String(p.getIpAddress()) !== "0.0.0.0") {
                return {ip: String(p.getIpAddress()), mask: String(p.getSubnetMask())}; } } catch(e){}
        }
        return null;
    }
    function bcastOf(ip, mask){
        var a = ip.split("."), m = mask.split("."), o = [];
        for (var i = 0; i < 4; i++) { o.push((parseInt(a[i],10) & parseInt(m[i],10)) | (~parseInt(m[i],10) & 255)); }
        return o.join(".");
    }
    // Status of each pair's PDU (UserTraffic: 1 running, 2 failed, 3 successful),
    // read from its first frame at or after n0. `seen` remembers how far the
    // buffer was scanned and each pair's first frame, so a check reads only the
    // frames added since the last one (rescanning everything froze PT for minutes
    // with 39 warm-up pings).
    function statuses(pairs, n0, seen){
        var s = S(), n = s.getFrameInstanceCount(), ok = 0, bad = 0, k, key;
        if (seen.next === undefined) { seen.next = n0; seen.at = {}; }
        for (var j = seen.next; j < n; j++) {
            try { var t = s.getFrameInstanceAt(j).getTrafficSource();
                if (t) { key = String(t.getCanonicalSource()) + ">" + String(t.getCanonicalDestination());
                    if (seen.at[key] === undefined) { seen.at[key] = j; } }
            } catch(e){}
        }
        seen.next = n;
        for (k = 0; k < pairs.length; k++) {
            var at = seen.at[pairs[k][0] + ">" + pairs[k][1]], code = 0;
            if (at !== undefined) { try { code = s.getFrameInstanceAt(at).getTrafficSource().getStatus(); } catch(e){} }
            if (code === 3) { ok++; } else if (code === 2) { bad++; }
        }
        return {successful: ok, failed: bad, total: pairs.length};
    }
    // End devices with a Command Prompt; servers by model, the rest are PCs.
    G.mcpDemoDevices = function(){
        var net = ipc.network(), n = net.getDeviceCount(), pcs = [], servers = [];
        for (var i = 0; i < n; i++) {
            var d = net.getDeviceAt(i);
            if (!d || typeof d.getCommandPrompt !== "function") { continue; }
            var name = String(d.getName()), model = String(d.getModel());
            (/server/i.test(model) ? servers : pcs).push(name);
        }
        var key = function(s){ var m = /^(.*?)(\d+)$/.exec(s); return m ? [m[1], parseInt(m[2],10)] : [s, -1]; };
        pcs.sort(function(a,b){ var x = key(a), y = key(b); return x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : x[1] - y[1]; });
        return J({pcs: pcs, servers: servers, window_sim: winSim()});
    };
    // Warm-up inside Simulation, stepped in this one call so nothing animates:
    // every pair pings once (passes repeat while some fail on a cold ARP cache),
    // so switches learn every port and routers every host; then the PDUs and
    // their frames are deleted. A Realtime warm-up showed as a flood of
    // envelopes on the Mac, where the window stays in Simulation.
    var WARM_MAX_MS = 8000;
    function warmUp(pairs){
        var s = S(), passes = 0, r = null, t0 = Date.now();
        for (var pass = 0; pass < 3; pass++) {
            var n0 = s.getFrameInstanceCount(), added = [], first = {}, steps = 0;
            for (var i = 0; i < pairs.length; i++) {
                if (U().addSimplePdu(pairs[i][0], pairs[i][1]) === 0) { added.push(pairs[i]); }
            }
            while (steps < 4000 && Date.now() - t0 < WARM_MAX_MS) {
                for (var k = 0; k < 25; k++) { s.forward(); steps++; }
                r = statuses(added, n0, first);
                if (r.successful + r.failed === added.length) { break; }
            }
            clearPdus();
            passes++;
            if ((r && r.successful === added.length) || Date.now() - t0 >= WARM_MAX_MS) { break; }
        }
        return {passes: passes, last: r};
    }
    // Simulation, Reset Simulation, ICMP only, the warm-up, then the demo's
    // traffic and Play.
    G.mcpDemoStart = function(arg){
        var a = JSON.parse(arg), s = S(), p = P(), i;
        pause();
        if (!s.isSimulationMode()) { s.setSimulationMode(true); }
        if (winSim() === false) { return J({ok: false, window_realtime: true}); }
        s.resetSimulation();
        clearPdus();
        var filters = ["ACL Filter", "ARP", "BGP", "Bluetooth", "CAPWAP", "CDP", "DHCP", "DHCPv6", "DNS", "DTP", "EAPOL", "EIGRP", "EIGRPv6", "FTP", "H.323", "HSRP", "HSRPv6", "HTTP", "HTTPS", "ICMP", "ICMPv6", "IEC", "IPSec", "ISAKMP", "IoT", "IoT TCP", "LACP", "LLDP", "MODBUS", "Meraki", "NDP", "NETFLOW", "NTP", "OSPF", "OSPFv6", "PAgP", "POP3", "PPP", "PPPoED", "PTP", "Profinet", "RADIUS", "REP", "RIP", "RIPng", "RTP", "SCCP", "SMTP", "SNMP", "SSH", "STP", "SYSLOG", "TACACS", "TCP", "TFTP", "Telnet", "UDP", "USB", "VTP"];
        for (i = 0; i < filters.length; i++) { try { p.setFilter(filters[i], filters[i] === "ICMP"); } catch(e){} }
        var warm = a.warm && a.warm.length ? warmUp(a.warm) : null;
        var st = {kind: a.kind, pairs: [], n0: s.getFrameInstanceCount(), first: {}, src: null, out0: 0};
        if (a.kind === "broadcast") {
            var d = ipc.network().getDevice(a.src), addr = d ? hostIp(d) : null;
            if (!addr) { return J({ok: false, error: "No IP address on " + a.src}); }
            var cp = d.getCommandPrompt();
            st.src = a.src; st.out0 = String(cp.getOutput()).length;
            st.target = bcastOf(addr.ip, addr.mask);
            cp.enterCommand("ping -n 1 " + st.target);
        } else {
            for (i = 0; i < a.pairs.length; i++) {
                if (U().addSimplePdu(a.pairs[i][0], a.pairs[i][1]) === 0) { st.pairs.push(a.pairs[i]); }
            }
            if (!st.pairs.length) { return J({ok: false, error: "PT refused every PDU"}); }
        }
        G.__mcpDemo = st;
        p.populateEventList();
        if (!p.isPlaying()) { p.play(); }
        return J({ok: true, pdus: st.pairs.length, target: st.target || null, warm: warm});
    };
    // Poll while Play runs: pause once every PDU ended, or when told to finish.
    G.mcpDemoTick = function(finish){
        var st = G.__mcpDemo, done, out = {};
        if (!st) { pause(); return J({done: true}); }
        if (st.kind === "broadcast") {
            var text = String(ipc.network().getDevice(st.src).getCommandPrompt().getOutput()).slice(st.out0);
            out.replies = (text.match(/Reply from/g) || []).length;
            done = /Ping statistics/.test(text);
        } else {
            out = statuses(st.pairs, st.n0, st.first);
            done = out.successful + out.failed === st.pairs.length;
        }
        if (done || finish) { pause(); try { P().populateEventList(); } catch(e){} G.__mcpDemo = null; }
        out.done = !!(done || finish); out.finished = !!done;
        return J(out);
    };
}

// The webview -> Script Engine IPC drops newlines, and the first // comment
// would then swallow the rest. As a JSON string literal the source is one line.
var SIM_ENGINE_JS = "(new Function(" + JSON.stringify("(" + simEngineHelpers.toString() + ")();") + "))();";

function simCall(fn, arg) {
    return $se("runCode", SIM_ENGINE_JS).then(function() {
        return arg === undefined ? $se(fn) : $se(fn, arg);
    }).then(function(raw) {
        try { return JSON.parse(raw); } catch (e) { return null; }
    });
}

function simSetStatus(text, cls) {
    var el = document.getElementById("sim-status");
    if (el) { el.textContent = text; el.className = "sim-status " + (cls || ""); }
}

function simFillSelect(id, names, preferred) {
    var sel = document.getElementById(id);
    if (!sel) { return; }
    var keep = sel.value;
    sel.innerHTML = "";
    names.forEach(function(n) {
        var o = document.createElement("option");
        o.value = n; o.textContent = n; sel.appendChild(o);
    });
    if (names.indexOf(keep) >= 0) { sel.value = keep; }
    else if (preferred && names.indexOf(preferred) >= 0) { sel.value = preferred; }
}

function simRefreshDevices() {
    try {
        simCall("mcpDemoDevices").then(function(d) {
            if (!d) { simSetStatus("Could not read the topology from PT.", "err"); return; }
            simFillSelect("sim-src", d.pcs, d.pcs[0]);
            simFillSelect("sim-dst", d.pcs, d.pcs[d.pcs.length - 1]);
            simFillSelect("sim-server", d.servers, d.servers[0]);
            SIM.pcs = d.pcs;
            var hint = d.window_sim === false
                ? " PT's window is in Realtime: click Simulation (bottom right of PT) once first."
                : "";
            simSetStatus(d.pcs.length + " PCs, " + d.servers.length + " server(s) found." + hint,
                         d.window_sim === false ? "warn" : "ok");
        }).catch(function(e) { simSetStatus("Script Engine error: " + e, "err"); });
    } catch (e) {
        simSetStatus("Script Engine unavailable.", "err");
    }
}

function simPairs(kind) {
    var src = val("sim-src"), dst = val("sim-dst"), srv = val("sim-server");
    var pcs = SIM.pcs || [];
    if (kind === "pc2pc") { return [[src, dst]]; }
    if (kind === "srv2pc") { return [[srv, dst]]; }
    if (kind === "srv2all") { return pcs.map(function(p) { return [srv, p]; }); }
    return [];  // broadcast: one ping from the source's Command Prompt
}

/* Every PC sends something first, so the switch learns every port: a ping to
   a PC whose MAC it does not know is flooded to all ports, and every other PC
   drops it with a red X (seen live, 190 drops for 20 pings). */
function simWarmPairs(kind) {
    var src = val("sim-src"), srv = val("sim-server"), pcs = SIM.pcs || [];
    var talk = srv ? pcs.map(function(p) { return [p, srv]; })
                   : pcs.filter(function(p) { return p !== src; }).map(function(p) { return [p, src]; });
    if (kind === "broadcast") {
        talk = talk.concat(pcs.filter(function(p) { return p !== src; }).map(function(p) { return [src, p]; }));
    }
    return talk.concat(simPairs(kind));
}

var SIM_LABELS = {
    broadcast: "Broadcast to all", pc2pc: "PC to PC",
    srv2pc: "Server to PC", srv2all: "Server to all PCs",
};

function simRun(kind) {
    if (SIM.running) { log("A simulation demo is already running", "warn"); return; }
    if (!SIM.pcs || !SIM.pcs.length) { simRefreshDevices(); log("Load the devices first (Refresh)", "warn"); return; }
    if ((kind === "srv2pc" || kind === "srv2all") && !val("sim-server")) {
        simSetStatus("This topology has no server.", "err"); return;
    }
    // At most SIM_BATCH PCs per Play run, each run after its own Reset
    // Simulation: PT's event buffer fills with time (background STP and the
    // like count too), and 20 pings at Play speed overflowed it (live).
    var pairs = simPairs(kind), batches = [];
    for (var i = 0; i < Math.max(pairs.length, 1); i += SIM_BATCH) { batches.push(pairs.slice(i, i + SIM_BATCH)); }
    SIM.kind = kind;
    SIM.batches = batches;
    SIM.batch = 0;
    SIM.totals = { successful: 0, failed: 0, total: 0 };
    SIM.warm = checked("sim-warm");
    SIM.maxMs = SIM_MAX_MS[kind];
    SIM.running = true;
    SIM.label = SIM_LABELS[kind];
    simSetButtons(true);
    log("Simulation demo: " + SIM.label + (batches.length > 1 ? " in " + batches.length + " batches of up to " + SIM_BATCH + " PCs" : ""), "cmd");
    simRunBatch();
}

function simBatchLabel() {
    return SIM.label + (SIM.batches.length > 1 ? " (batch " + (SIM.batch + 1) + " of " + SIM.batches.length + ")" : "");
}

function simRunBatch() {
    var kind = SIM.kind, pairs = SIM.batches[SIM.batch];
    // The warm-up runs inside the start call, stepped without animation: every
    // PC talks once so the switch knows every port (no flooding, no red X's).
    var warm = !SIM.warm ? [] : simWarmPairs(kind).filter(function(p) {
        return simPairs(kind).every(function(q) { return q[0] !== p[0] || q[1] !== p[1]; });
    }).concat(pairs);
    var arg = { kind: kind, pairs: kind === "broadcast" ? [] : pairs, src: val("sim-src"), warm: warm };
    simSetStatus(simBatchLabel() + ": resetting the simulation and warming up…", "");
    simCall("mcpDemoStart", JSON.stringify(arg)).then(function(r) {
        if (!r) { simFail("no answer from PT"); return; }
        if (r.window_realtime) {
            simDone();
            simSetStatus("PT's window is in Realtime. Click Simulation (bottom right of PT), then press the demo again.", "warn");
            showNotif("Click Simulation in Packet Tracer (bottom right), then press the demo again.");
            return;
        }
        if (!r.ok) { simFail(r.error || "PT refused the demo"); return; }
        simSetStatus(simBatchLabel() + ": playing…" + (r.target ? " (ping " + r.target + ")" : ""), "ok");
        SIM.t0 = Date.now();
        SIM.timer = setTimeout(tick, SIM_TICK_MS);
    }).catch(simFail);
}

function tick() {
    var finish = Date.now() - SIM.t0 > SIM.maxMs;
    simCall("mcpDemoTick", finish ? "finish" : "").then(function(r) {
        if (!r) { simFail("no answer from PT (is a PT dialog open?)"); return; }
        var progress = r.total !== undefined
            ? r.successful + " successful, " + r.failed + " failed of " + r.total
            : (r.replies || 0) + " replies";
        if (!r.done) {
            simSetStatus(simBatchLabel() + ": playing… " + progress, "ok");
            SIM.timer = setTimeout(tick, SIM_TICK_MS);
            return;
        }
        if (r.total !== undefined) {
            SIM.totals.successful += r.successful; SIM.totals.failed += r.failed; SIM.totals.total += r.total;
        }
        if (r.finished && SIM.batch + 1 < SIM.batches.length) {
            log(simBatchLabel() + " finished: " + progress, "ok");
            SIM.batch++;
            simRunBatch();
            return;
        }
        simDone();
        if (SIM.batches.length > 1) {
            var t = SIM.totals;
            progress = t.successful + " successful, " + t.failed + " failed of " + t.total;
        }
        var text = SIM.label + (r.finished ? " finished: " : " stopped: ") + progress + ". Play paused.";
        simSetStatus(text, r.failed || !r.finished ? "warn" : "ok");
        log(text, r.failed || !r.finished ? "warn" : "ok");
    }).catch(simFail);
}

function simStop() {
    if (!SIM.running) { return; }
    if (SIM.timer) { clearTimeout(SIM.timer); SIM.timer = null; }
    SIM.t0 = 0;  // the next tick finishes and pauses
    tick();
}

function simDone() {
    if (SIM.timer) { clearTimeout(SIM.timer); SIM.timer = null; }
    SIM.running = false;
    simSetButtons(false);
}

function simFail(e) {
    simDone();
    simSetStatus("Demo failed: " + e, "err");
    log("Simulation demo failed: " + e, "err");
    try { $se("runCode", "try{var p=ipc.appWindow().getSimulationPanel();if(p.isPlaying()){p.play();}}catch(e){}"); } catch (x) {}
}

function simSetButtons(busy) {
    document.querySelectorAll(".sim-demo-btn").forEach(function(b) { b.disabled = busy; });
    var stop = document.getElementById("sim-stop");
    if (stop) { stop.disabled = !busy; }
}


// ------------------------------------------------------- Notifications -----

function showNotif(msg) {
    var strip = document.getElementById("notifStrip");
    var msgEl = document.getElementById("notifMsg");
    if (strip && msgEl) {
        msgEl.textContent = msg;
        strip.classList.add("active");
        setTimeout(closeNotif, 8000);
    }
}

function closeNotif() {
    var strip = document.getElementById("notifStrip");
    if (strip) strip.classList.remove("active");
}

// ------------------------------------------------------- Utilities ---------

function setElText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
}

function setElClass(id, cls) {
    var el = document.getElementById(id);
    if (el) el.className = cls;
}

function setCardClass(id, cls) {
    var el = document.getElementById(id);
    if (el) el.className = cls;
}

function val(id) {
    var el = document.getElementById(id);
    return el ? el.value : "";
}

function intVal(id) {
    return parseInt(val(id), 10) || 0;
}

function checked(id) {
    var el = document.getElementById(id);
    return el ? el.checked : false;
}

function pad2(n) {
    return n < 10 ? "0" + n : "" + n;
}

function escapeHtml(str) {
    var d = document.createElement("div");
    d.appendChild(document.createTextNode(String(str)));
    return d.innerHTML;
}

function escapeRe(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}