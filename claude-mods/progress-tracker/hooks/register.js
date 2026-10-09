import { atom, read } from 'claude-code'
import { segmentSvg, terminalCells } from './ledger.js'
import { parseIndex, parsePhase, parseGeneric, buildModel, shortName } from './parse-plan.js'

const DEFAULT_COLOR = 0x01000000
const CYAN = 0x35d6ff
const PURPLE = 0xc77dff

// Both bars take this share of the band's width, on the desktop and in a terminal, whatever
// the number of tasks or steps: segments share the width.
const BAR_SHARE = 0.7
// The band is measured in cells of the desktop's code font; a segment's SVG needs CSS px.
// Measured 5 Oct 2026 from a screenshot: the 5-cell label plus its 1-cell gap were 52 px
// at the app's ~109% zoom, so about 8 CSS px a cell.
const CELL_PX = 8
// Names beside the bars show at most this many words; the full text shows on hover.
const NAME_WORDS = 5
// The desktop band's background (dark theme), behind a hover readout that covers a row
const BAND_BG = '#212121'
const SEG_H = 22
// How long an animation's markup stays in a segment before it is drawn plain again
const GROW_MS = 900
const STEP_MS = 1400
const TASK_MS = 3400
const PLAN_MS = 4400
// File checks while a turn runs, so ticks show as they land, not when the reply ends
const POLL_MS = 2500
const RESCAN_MS = 15000

// The band's open/closed switch, owned by cost-ticker; while closed this mod draws nothing
const barOpen = atom({ plugin: 'cost-ticker', key: 'barOpen' }, true)

// The plan the bars show: { source, file, phases, current, percent }
let model = null
let modelFile = null
let modelMtime = 0
// TodoWrite list, the fallback when there is no plan file
let todos = []
// The step being worked on (first open box of the focus task) and the work seen since it
// opened: tool calls weighted by how much they move a step along.
let active = { key: '', weight: 0 }
// Last drawn fill per segment, and animations due: key -> { from?, anim?, shimmer?, until }
const fills = new Map()
const anims = new Map()
let lastLoad = 0

const num = (i) => String(i).padStart(2, '0')
const clip = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s)
const now = () => Date.now()

const WEIGHT = { Edit: 3, Write: 3, MultiEdit: 3, NotebookEdit: 3, Bash: 2, PowerShell: 2 }
// Work seen on a step → how far along it probably is. Never reaches the end: only a tick does.
const estimate = (w) => 0.9 * (1 - Math.exp(-w / 24))

// Phase files (PLAN/INDEX.md + PLAN/phases/*.md), else the newest plan file, else nothing
async function findPlan($) {
  const cwd = await $.session.cwd()
  const indexPath = cwd + '/PLAN/INDEX.md'
  if (await $.fs.exists(indexPath)) return { kind: 'phases', file: indexPath, cwd }
  // Plan files: PLAN.md, the files in the usual plan folders, and top-level *.md
  // whose first heading says "plan" (e.g. INSPi.md). The newest that parses wins.
  const found = []
  for (const file of [cwd + '/PLAN.md', cwd + '/plan.md']) {
    if (await $.fs.exists(file)) found.push({ file, mtimeMs: (await $.fs.stat(file)).mtimeMs })
  }
  for (const dir of ['/docs/superpowers/plans', '/docs/plans', '/plans', '/PLAN']) {
    if (!(await $.fs.exists(cwd + dir))) continue
    for (const f of await $.fs.list(cwd + dir)) {
      if (f.kind === 'file' && /\.md$/i.test(f.name) && f.name !== 'INDEX.md') found.push({ file: cwd + dir + '/' + f.name, mtimeMs: f.mtimeMs })
    }
  }
  for (const f of await $.fs.list(cwd)) {
    if (f.kind !== 'file' || !/\.md$/i.test(f.name) || /^(plan|readme|changelog|claude|agents|buildlog)\.md$/i.test(f.name)) continue
    const head = (await $.fs.read(cwd + '/' + f.name)).slice(0, 400)
    if (/^#\s+.*\bplan\b/im.test(head)) found.push({ file: cwd + '/' + f.name, mtimeMs: f.mtimeMs })
  }
  found.sort((a, b) => b.mtimeMs - a.mtimeMs)
  for (const { file } of found) {
    if (parseGeneric(await $.fs.read(file)).some((u) => u.total > 0)) return { kind: 'file', file, cwd }
  }
  return null
}

async function readPlan($, plan) {
  if (plan.kind === 'phases') {
    const rows = parseIndex(await $.fs.read(plan.file))
    const units = []
    for (const row of rows) {
      const file = plan.cwd + '/PLAN/' + row.path
      const there = await $.fs.exists(file)
      const phase = there ? parsePhase(await $.fs.read(file)) : { title: '', checked: 0, total: 0, boxes: [] }
      const mtimeMs = there ? (await $.fs.stat(file)).mtimeMs : 0
      units.push({ ...phase, title: row.title || phase.title, done: row.done, mtimeMs })
    }
    return rows.length ? { source: 'phases', file: plan.file, ...buildModel(units) } : null
  }
  return { source: 'file', file: plan.file, ...buildModel(parseGeneric(await $.fs.read(plan.file))) }
}

// Each todo is a one-box phase; the in-progress one is the focus
function todoModel() {
  if (todos.length === 0) return null
  const m = buildModel(todos.map((t) => ({ title: t.content, checked: t.status === 'completed' ? 1 : 0, total: 1, done: false })))
  return { source: 'todos', file: 'todos', ...m, current: todos.findIndex((t) => t.status === 'in_progress') }
}

// The open step of the focus task, as an index into its boxes (-1 when none)
function activeStep(m) {
  const cur = m.current >= 0 ? m.phases[m.current] : null
  if (!cur || cur.complete) return -1
  return cur.boxes.findIndex((b) => !b.checked)
}

// What each segment shows: plan segments (one per task) and task segments (one per step)
function layout(m) {
  const cur = m.current >= 0 ? m.phases[m.current] : null
  const step = activeStep(m)
  const key = cur && step >= 0 ? `${m.file}#${cur.index}#${step}` : ''
  if (key !== active.key) active = { key, weight: 0 }
  const partial = key ? estimate(active.weight) : 0

  const steps = cur
    ? cur.boxes.map((b, j) => ({
        key: `t:${m.file}#${cur.index}#${j}`,
        fill: cur.complete || b.checked ? 1 : j === step ? partial : 0,
        checkpoint: cur.complete || b.checked ? 'done' : j === step ? 'focus' : 'open',
        text: b.text,
        weight: 1,
      }))
    : []
  const tasks = m.phases.map((p, i) => {
    const total = p.total || 1
    const have = p.complete ? total : p.checked + (i === m.current ? partial : 0)
    return {
      key: `p:${m.file}#${i}`,
      fill: have / total,
      checkpoint: p.complete ? 'done' : i === m.current ? 'focus' : 'open',
      text: `${num(i)} · ${p.title}${p.total ? `  ${p.checked}/${p.total}` : ''}`,
      weight: Math.max(1, Math.sqrt(total)),
    }
  })
  let have = 0
  let all = 0
  for (const t of tasks) {
    const total = m.phases[tasks.indexOf(t)].total || 1
    all += total
    have += t.fill * total
  }
  return { cur, step, steps, tasks, percent: all ? have / all : 0 }
}

function schedule($, key, value, ms) {
  anims.set(key, { ...anims.get(key), ...value, until: now() + ms })
  $.clock.after(ms + 60, () => $.ui.invalidate('ui.render'))
}

// Compares the new drawing with the last one: fills that grew get a grow animation, steps
// and tasks that just finished get theirs, and the plan finishing sets off the biggest.
function noteChanges($, before, after, sameSource) {
  for (const seg of [...after.tasks, ...after.steps]) {
    const prev = fills.get(seg.key)
    fills.set(seg.key, seg.fill)
    if (prev != null && seg.fill > prev + 0.004) schedule($, seg.key, { from: prev }, GROW_MS)
  }
  if (!before || !sameSource) return
  after.steps.forEach((s, j) => {
    const was = before.steps.find((b) => b.key === s.key)
    if (was && was.checkpoint !== 'done' && s.checkpoint === 'done') schedule($, s.key, { anim: 'step' }, STEP_MS)
  })
  let tasksDone = 0
  after.tasks.forEach((t, i) => {
    const was = before.tasks[i]
    if (was && was.checkpoint !== 'done' && t.checkpoint === 'done') {
      tasksDone++
      schedule($, t.key, { anim: 'task', shimmer: true }, TASK_MS)
      for (const s of before.cur && before.cur.index === i ? before.steps : []) schedule($, s.key, { shimmer: true }, TASK_MS)
      $.ui.toast(`✦ Task ${num(i)} done: ${clip(model?.phases[i]?.title ?? '', 60)}`)
    }
  })
  const wasDone = before.tasks.length > 0 && before.tasks.every((t) => t.checkpoint === 'done')
  const isDone = after.tasks.length > 0 && after.tasks.every((t) => t.checkpoint === 'done')
  if (isDone && !wasDone) {
    for (const t of after.tasks) schedule($, t.key, { anim: 'plan', shimmer: true }, PLAN_MS)
    $.ui.toast('✦✦ Plan complete. Every task is done.', { timeoutMs: 6000 })
  }
  return tasksDone
}

let drawn = null
async function refresh($, { rescan = false } = {}) {
  lastLoad = now()
  try {
    const plan = rescan || !modelFile ? await findPlan($) : { kind: modelFile.endsWith('/PLAN/INDEX.md') ? 'phases' : 'file', file: modelFile, cwd: await $.session.cwd() }
    const next = plan ? await readPlan($, plan) : null
    modelFile = next ? next.file : null
    modelMtime = next && next.source === 'file' ? (await $.fs.stat(next.file)).mtimeMs : modelMtime
    model = next
  } catch {
    // A file that vanished or could not be read: keep what is drawn (or the todo list)
  }
  redraw($)
}

function redraw($) {
  const m = model ?? todoModel()
  const after = m && m.phases.length ? layout(m) : null
  if (after) noteChanges($, drawn, after, drawn != null && drawn.file === m.file)
  drawn = after ? { ...after, file: m.file } : null
  $.ui.invalidate('ui.render')
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    await refresh($, { rescan: true })
    // Ticks made by any means (an editor, sed, another tool) show within a few seconds
    $.clock.every(POLL_MS, async () => {
      if (!modelFile || modelFile === 'todos') return
      if (!(await $.fs.exists(modelFile))) return refresh($, { rescan: true })
      const mtime = (await $.fs.stat(modelFile)).mtimeMs
      if (mtime !== modelMtime) await refresh($)
    })
    // A newer plan file (a new plan was written) takes over
    $.clock.every(RESCAN_MS, () => refresh($, { rescan: true }))
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    await refresh($, { rescan: true })
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    if (e.tool === 'TodoWrite') {
      const list = e.todos ?? (e.input && e.input.todos)
      if (Array.isArray(list)) todos = list
    }
    const result = await next(e)
    // Work on the open step moves its fill along a little
    active.weight += WEIGHT[e.tool] ?? 1
    const path = String(e.file_path ?? (e.input && e.input.file_path) ?? '')
    if (/\.md$/i.test(path) || now() - lastLoad > 800) await refresh($, { rescan: /\.md$/i.test(path) && path !== modelFile })
    else redraw($)
    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const rest = await next(e)
    const m = model ?? todoModel()
    const d = drawn
    if (!m || !d || !(await read($, barOpen))) return rest
    const { Box, Text, Raster, Svg } = $.ui.resolve(e)
    const t = now()
    const due = (key) => {
      const a = anims.get(key)
      if (a && a.until > t) return a
      if (a) anims.delete(key)
      return null
    }

    // Both bars are BAR_SHARE of the band; the name beside the task bar gets what is left
    const cols = e.props?.bodyColumns ?? e.viewport?.columns ?? 96
    const barCells = Math.max(16, Math.round(cols * BAR_SHARE))
    const barPx = barCells * CELL_PX
    const room = Math.max(8, cols - 5 - barCells - 3)

    // Hover readouts (desktop): the full text over the other row, full width, on the band's own
    // background, so a step's text covers the plan row and a task's covers the task row.
    const overlays = []
    const reveal = (scope, text, row) => {
      if (e.surface !== 'desktop' || !text) return
      overlays.push(
        Box({
          key: 'ov-' + scope,
          position: 'absolute',
          top: row === 0 ? 1 : 0,
          left: 0,
          width: '100%',
          display: 'none',
          backgroundColor: BAND_BG,
          hover: { scope, display: 'flex' },
          children: [Text({ wrap: 'truncate', children: [text] })],
        }),
      )
    }

    const bar = (segs, color, prefix) => {
      if (e.surface === 'desktop') {
        const total = segs.reduce((s, x) => s + x.weight, 0)
        return Box({
          flexDirection: 'row',
          flexShrink: 0,
          children: segs.map((s, i) => {
            const width = (barPx * s.weight) / total
            const a = due(s.key)
            reveal(prefix + i, s.text, prefix === 'ph' ? 0 : 1)
            return Box({
              key: prefix + i,
              hover: { scope: prefix + i },
              children: [
                Svg({
                  source: segmentSvg({
                    width,
                    height: SEG_H,
                    fill: s.fill,
                    from: a?.from,
                    color,
                    checkpoint: s.checkpoint,
                    anim: a?.anim ?? null,
                    shimmer: Boolean(a?.shimmer),
                    first: i === 0,
                    last: i === segs.length - 1,
                  }),
                  alt: s.text,
                  width,
                  height: SEG_H,
                }),
              ],
            })
          }),
        })
      }
      if (e.surface === 'terminal') {
        const total = segs.reduce((s, x) => s + x.weight, 0)
        let left = barCells
        const cells = segs.map((s, i) => {
          const cols = i === segs.length - 1 ? Math.max(2, left) : Math.max(2, Math.round((barCells * s.weight) / total))
          left -= cols
          const a = due(s.key)
          const lit = a?.anim === 'plan' ? 0xffd166 : a?.anim ? 0xffffff : color
          return { cols, fill: s.fill, checkpoint: s.checkpoint, color: lit }
        })
        const columns = cells.reduce((s, c) => s + c.cols, 0)
        return Raster({ key: prefix, columns, rows: 1, cells: terminalCells(cells, DEFAULT_COLOR) })
      }
      return Text({ color: 'cyan', children: [segs.map((s) => (s.checkpoint === 'done' ? '◆' : s.fill > 0 ? '◈' : '◇')).join('─')] })
    }

    const todo = m.source === 'todos'
    const cur = d.cur
    // Beside the task bar: at most NAME_WORDS words of the task's name, as many as fit (desktop
    // text is proportional: about 1.3 characters to a cell of the code font). Hovering it shows
    // the number, the count, the whole name and the open step.
    let label = 'plan complete'
    if (cur) {
      const stepText = d.step >= 0 ? cur.boxes[d.step]?.text ?? '' : ''
      const count = todo ? `${d.tasks.filter((s) => s.checkpoint === 'done').length}/${d.tasks.length}` : `${cur.checked}/${cur.total}`
      label = shortName(cur.title, Math.floor(room * (e.surface === 'desktop' ? 1.3 : 1)), NAME_WORDS)
      reveal('label', todo ? `${count}  ${cur.title}` : `${num(cur.index)} · ${count}  ${cur.title}${stepText ? `  → ${stepText}` : ''}`, 1)
    }

    const planRow = Box({
      flexDirection: 'row',
      columnGap: 1,
      alignItems: 'center',
      children: [
        Box({ width: 5, flexShrink: 0, children: [Text({ dimColor: true, children: ['plan'] })] }),
        bar(d.tasks, CYAN, 'ph'),
        Text({ children: [`${Math.round(d.percent * 100)}%`] }),
      ],
    })
    const taskRow = Box({
      flexDirection: 'row',
      columnGap: 1,
      alignItems: 'center',
      children: [
        Box({ width: 5, flexShrink: 0, children: [Text({ dimColor: true, children: ['task'] })] }),
        ...(cur ? [bar(todo ? d.tasks : d.steps, PURPLE, 'cr')] : []),
        Box({ key: 'label', flexShrink: 1, minWidth: 0, hover: { scope: 'label' }, children: [Text({ wrap: 'truncate', children: [label] })] }),
      ],
    })

    return Box({
      flexDirection: 'column',
      children: [planRow, taskRow, ...overlays, ...(rest ? [rest] : [])],
    })
  })
}
