// Pure functions: turn Claude's plan files into phases with checklist counts.

const BOX = /^\s*[-*]\s*\[( |x|X)\]\s*(.*)$/

// The first words of a name: at most `max` of them, and as many as fit in `room` characters
// (always at least one). Ends in "…" when anything was left out.
export function shortName(text, room = Infinity, max = 5) {
  const words = String(text).trim().split(/\s+/).filter(Boolean)
  const kept = []
  for (const word of words.slice(0, max)) {
    const next = [...kept, word].join(' ')
    if (kept.length && next.length + 1 > room) break
    kept.push(word)
  }
  if (kept.length === words.length) return kept.join(' ')
  return kept.join(' ').replace(/[\s,;:.·→—–-]+$/, '') + '…'
}

function plain(text) {
  return text
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[*_`]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

// Every checkbox in order: { checked, text }
export function countBoxes(text) {
  const boxes = []
  for (const line of text.split(/\r?\n/)) {
    const m = BOX.exec(line)
    if (m) boxes.push({ checked: m[1] !== ' ', text: plain(m[2]) })
  }
  return { checked: boxes.filter((b) => b.checked).length, total: boxes.length, boxes }
}

// The text under "## Acceptance criteria", or the whole file when it has none
function acceptanceSection(text) {
  const lines = text.split(/\r?\n/)
  const start = lines.findIndex((l) => /^##\s+acceptance/i.test(l))
  if (start < 0) return text
  let end = lines.length
  for (let i = start + 1; i < lines.length; i++) {
    if (/^##\s/.test(lines[i])) {
      end = i
      break
    }
  }
  return lines.slice(start, end).join('\n')
}

function cleanTitle(raw) {
  return raw
    .replace(/\*\*/g, '')
    .replace(/^PHASE-\d+\s*[—–-]\s*/i, '')
    .replace(/\s+/g, ' ')
    .trim()
}

// "| [00](phases/PHASE-00.md) | Title | deps | output (**done**) |" rows
export function parseIndex(text) {
  const rows = []
  for (const line of text.split(/\r?\n/)) {
    const m = /^\|\s*\[(\d+)\]\(([^)]+)\)\s*\|\s*([^|]*)\|(.*)$/.exec(line)
    if (!m) continue
    rows.push({
      num: Number(m[1]),
      path: m[2],
      title: cleanTitle(m[3]),
      done: /\(\*\*done\*\*\)|\(done\)/i.test(m[4]),
    })
  }
  return rows
}

export function parsePhase(text) {
  const heading = /^#\s+(.+)$/m.exec(text)
  return { title: heading ? cleanTitle(heading[1]) : '', ...countBoxes(acceptanceSection(text)) }
}

const SKIP = /^(context|verification|files?|risks?|open questions?|findings?|build order|remaining|summary|notes?)\b/i

// A plan without phase files. Tried in order:
// 1. a "Milestones"/"Phases" section of bold "**M0 — Title**" lines (INSPi.md style),
//    done per "(done)"/✅ on the line or a status line like "M0–M4 done";
// 2. the heading level ("## " or "### ", e.g. superpowers "### Task N") holding the
//    most checkboxes, each heading a unit and its checkboxes the subtasks.
export function parseGeneric(text) {
  const ms = parseMilestones(text)
  if (ms.length > 0) return ms
  let best = []
  let bestBoxes = -1
  for (const level of [2, 3]) {
    const units = headingUnits(text, level)
    // Units that carry checkboxes, so a "## " wrapping every "### Task" loses
    const boxes = units.filter((u) => u.total > 0).length
    if (units.length > 0 && boxes > bestBoxes) {
      best = units
      bestBoxes = boxes
    }
  }
  return best
}

function headingUnits(text, level) {
  const own = new RegExp('^#{' + level + '}\\s+(.+)$')
  const stop = new RegExp('^#{1,' + level + '}\\s')
  const units = []
  let cur = null
  for (const line of text.split(/\r?\n/)) {
    const h = own.exec(line)
    if (h) {
      const title = cleanTitle(h[1]).replace(/^\d+[.)]\s+/, '')
      cur = SKIP.test(title) ? null : { title, lines: [] }
      if (cur) units.push(cur)
    } else if (stop.test(line)) cur = null
    else if (cur) cur.lines.push(line)
  }
  return units.map((u) => ({ title: u.title, ...countBoxes(u.lines.join('\n')), done: false }))
}

// "M0–M4 done, M5–M6 mostly done" → { done: {M0..M4}, partial: {M5, M6} }
function milestoneDone(text) {
  const done = new Set()
  const partial = new Set()
  const re = /\b([A-Z]{1,2})(\d+)(?:\s*[–—-]\s*\1?(\d+))?\s+(mostly |partly |partially )?done\b/g
  for (const m of text.matchAll(re)) {
    const a = Number(m[2])
    const b = m[3] != null ? Number(m[3]) : a
    for (let n = a; n <= b; n++) (m[4] ? partial : done).add(m[1] + n)
  }
  return { done, partial }
}

export function parseMilestones(text) {
  const lines = text.split(/\r?\n/)
  const start = lines.findIndex((l) => /^#{1,3}\s+(\d+[.)]\s+)?(milestones|phases|roadmap)\b/i.test(l))
  if (start < 0) return []
  const level = /^#+/.exec(lines[start])[0].length
  const end = new RegExp('^#{1,' + level + '}\\s')
  const { done, partial } = milestoneDone(text)
  const units = []
  for (let i = start + 1; i < lines.length; i++) {
    if (end.test(lines[i])) break
    const m = /^\s*\*\*\s*((?:[A-Z]{1,2}\d+|Phase\s+\d+|Milestone\s+\d+)\s*[—–:-]\s*[^*]+)\*\*(.*)$/i.exec(lines[i])
    if (!m) continue
    const id = /^([A-Z]{1,2}\d+)/i.exec(m[1])?.[1].toUpperCase()
    const full = /\(\*{0,2}done\*{0,2}\)|✅|\[x\]/i.test(m[2]) || (id != null && done.has(id))
    const half = !full && id != null && partial.has(id)
    units.push({ title: m[1].trim(), checked: full || half ? 1 : 0, total: half ? 2 : 1, done: full })
  }
  return units
}

// units: [{ title, checked, total, boxes?, done, mtimeMs? }] in plan order.
// Phases are often finished out of order, so the focus is the open phase whose
// file changed last (where work is happening), not the first open one.
export function buildModel(units) {
  const phases = units.map((u, i) => {
    const complete = u.done || (u.total > 0 && u.checked === u.total)
    const fraction = complete ? 1 : u.total ? u.checked / u.total : 0
    const boxes = u.boxes ?? [{ checked: complete, text: u.title }]
    return { index: i, title: u.title, checked: u.checked, total: u.total, complete, fraction, boxes, mtimeMs: u.mtimeMs ?? 0 }
  })
  let current = -1
  for (const p of phases) {
    if (p.complete) continue
    if (current < 0 || p.mtimeMs > phases[current].mtimeMs) current = p.index
  }
  let have = 0
  let all = 0
  for (const p of phases) {
    const t = p.total || 1
    all += t
    have += p.complete ? t : p.checked
  }
  return { phases, current, percent: all ? have / all : 0 }
}
