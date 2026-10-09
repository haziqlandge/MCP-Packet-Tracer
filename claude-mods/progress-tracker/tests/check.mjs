// node tests/check.mjs <repo> [preview.html]: prints the parsed plan; with a second
// argument, writes the desktop strips to an HTML page for a look in a browser.
import fs from 'fs'
import path from 'path'
import { parseIndex, parsePhase, buildModel } from '../hooks/parse-plan.js'
import { segmentSvg } from '../hooks/ledger.js'
const [root, out] = process.argv.slice(2)
const idx = parseIndex(fs.readFileSync(path.join(root, 'PLAN/INDEX.md'), 'utf8'))
const units = idx.map((r) => {
  const file = path.join(root, 'PLAN', r.path)
  const p = parsePhase(fs.readFileSync(file, 'utf8'))
  return { ...p, title: r.title || p.title, done: r.done, mtimeMs: fs.statSync(file).mtimeMs }
})
const m = buildModel(units)
for (const p of m.phases) console.log(String(p.index).padStart(2), p.complete ? 'DONE' : 'open', `${p.checked}/${p.total}`, p.title)
console.log('focus', m.current, 'percent', (m.percent * 100).toFixed(1))
if (out) {
  // Same shapes as the desktop band: each bar 300px, a segment per task / step
  const seg = (items, color) => {
    const total = items.reduce((a, x) => a + x.w, 0)
    return items
      .map((x, i) => segmentSvg({ width: (300 * x.w) / total, height: 22, fill: x.fill, color, checkpoint: x.cp, anim: null, shimmer: false, first: i === 0, last: i === items.length - 1 }))
      .join('')
  }
  const plan = seg(m.phases.map((p, i) => ({ w: Math.max(1, Math.sqrt(p.total || 1)), fill: p.fraction, cp: p.complete ? 'done' : i === m.current ? 'focus' : 'open' })), 0x35d6ff)
  const cur = m.phases[m.current]
  const open = cur ? cur.boxes.findIndex((b) => !b.checked) : -1
  const task = cur ? seg(cur.boxes.map((b, j) => ({ w: 1, fill: b.checked ? 1 : 0, cp: b.checked ? 'done' : j === open ? 'focus' : 'open' })), 0xc77dff) : ''
  const row = (name, bar, text) => `<div class="r"><span class="n">${name}</span><span class="b">${bar}</span><span>${text}</span></div>`
  fs.writeFileSync(
    out,
    `<!doctype html><meta charset="utf-8"><style>body{background:#262624;color:#eee;font:14px system-ui;padding:24px}.r{display:flex;align-items:center;gap:8px;margin:6px 0}.n{color:#888;width:36px}.b{display:flex}.b svg{display:block}</style>` +
      row('plan', plan, `${Math.round(m.percent * 100)}%`) +
      row('task', task, cur ? `${String(cur.index).padStart(2, '0')} · ${cur.checked}/${cur.total}&nbsp; ${cur.title}` : 'plan complete'),
  )
}
