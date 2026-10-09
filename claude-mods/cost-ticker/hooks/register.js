import { atom, read, update } from 'claude-code'

const TEAL = 0x16c9b4
const NEON_GREEN = 0xb6ff5e

// Totals across the session, and the last turn alone
let total = { input: 0, output: 0, read: 0, write: 0 }
let last = null
let usd = 0
// Whether the mods' band is open. This mod owns it; cache-timer and progress-tracker read it
// and draw nothing while it is closed. The last choice is remembered for new sessions.
const barOpen = atom({ plugin: 'cost-ticker', key: 'barOpen' }, true)

// This month's spend over every session that ran this mod, and the day counting began
let month = { usd: 0, since: null }

function mix(a, b, t) {
  const ch = (s) => Math.round(((a >> s) & 255) * (1 - t) + ((b >> s) & 255) * t)
  return (ch(16) << 16) | (ch(8) << 8) | ch(0)
}

function hex(n) {
  return '#' + n.toString(16).padStart(6, '0')
}

function rate(u) {
  const all = u.input + u.read + u.write
  return all > 0 ? u.read / all : 0
}

function k(n) {
  return n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'k' : String(n)
}

// Local calendar dates, so the month turns over at your midnight, not UTC's
const pad = (n) => String(n).padStart(2, '0')
const dayOf = (ms) => {
  const d = new Date(ms)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
const monthOf = (ms) => dayOf(ms).slice(0, 7)

// Each session keeps its own store key per month, `m:<YYYY-MM>:<session>` = { spent, last },
// so sessions never write over each other; the month is the sum of its keys. `spent` grows
// by the change in the session's cost since `last`, so a session that spans a month boundary
// counts in each month only what it spent there, and one whose cost restarts (a resume in a
// new process) adds its new cost instead of going negative.
async function recordMonth($, processUsd) {
  const now = await $.clock.now()
  const ym = monthOf(now)
  const sid = await $.session.id()
  const key = `m:${ym}:${sid}`
  let entry = await $.store.get(key)
  const isNew = !entry
  if (isNew) {
    const prev = await $.store.get(`m:${monthOf(new Date(Number(ym.slice(0, 4)), Number(ym.slice(5, 7)) - 1, 1).getTime() - 1)}:${sid}`)
    entry = { spent: 0, last: prev ? prev.last : 0 }
  }
  const delta = processUsd >= entry.last ? processUsd - entry.last : processUsd
  if (delta > 0 || isNew) await $.store.set(key, { spent: entry.spent + delta, last: processUsd })

  let since = await $.store.get('since')
  if (!since) {
    since = dayOf(now)
    await $.store.set('since', since)
  }
  let sum = 0
  for (const name of await $.store.keys()) {
    if (!name.startsWith(`m:${ym}:`)) continue
    const v = await $.store.get(name)
    if (v && typeof v.spent === 'number') sum += v.spent
  }
  month = { usd: sum, since: since.slice(0, 7) === ym && !since.endsWith('-01') ? since : null }
}

// The engine's cost is this process's alone: closing Claude and opening the session again
// starts it from $0. So each session keeps a ledger, `s:<session>` = { carried, last, total,
// lastTurn }: when the process's cost comes back lower than the last one seen, the process
// restarted and what it had reached is carried into the session's figure. Token totals ride
// along so the cost row survives a restart (and a hot reload) too.
async function sessionLedger($, processUsd) {
  const sid = await $.session.id()
  const key = `s:${sid}`
  const entry = (await $.store.get(key)) ?? (await seedLedger($, sid, processUsd))
  if (processUsd + 1e-9 < entry.last) entry.carried += entry.last
  entry.last = processUsd
  entry.total = total
  entry.lastTurn = last
  await $.store.set(key, entry)
  return entry.carried + processUsd
}

// A session older than its ledger: the month records (`m:<YYYY-MM>:<session>`) already hold
// what it spent, earlier processes included, so the ledger starts from their sum. Whatever the
// newest record saw of this very process is left out, since it is counted again from here.
// (Runs before this refresh's month record, so the records are the previous refresh's.)
async function seedLedger($, sid, processUsd) {
  let spent = 0
  let newest = null
  for (const name of await $.store.keys()) {
    if (!name.startsWith('m:') || !name.endsWith(':' + sid)) continue
    const v = await $.store.get(name)
    if (!v || typeof v.spent !== 'number') continue
    spent += v.spent
    if (!newest || name > newest.name) newest = { name, last: v.last ?? 0 }
  }
  const sameProcess = newest != null && processUsd + 1e-9 >= newest.last
  return { carried: Math.max(0, spent - (sameProcess ? newest.last : 0)), last: processUsd }
}

async function loadLedger($) {
  try {
    const entry = await $.store.get(`s:${await $.session.id()}`)
    if (entry && entry.total) total = { ...total, ...entry.total }
    if (entry && entry.lastTurn) last = entry.lastTurn
  } catch {}
}

async function refresh($) {
  const usage = await $.session.usage()
  const processUsd = usage.cost ? usage.cost.usd : 0
  usd = processUsd
  try {
    usd = await sessionLedger($, processUsd)
  } catch {}
  // The month total is a bonus: a store that fails must not stall the session figure
  try {
    await recordMonth($, processUsd)
  } catch {}
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const sinceLabel = (iso) => ` (since ${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]})`

export function register(on) {
  on('session.start', async ($, e, next) => {
    // The footer row below replaces the old status line
    $.ui.status(undefined)
    const remembered = await $.store.get('barOpen')
    if (remembered === false) await update($, barOpen, () => false)
    await loadLedger($)
    await refresh($)
    return next(e)
  })

  // Every model request inside a turn (subagents' too) counts as soon as its response
  // is whole, so the figures move while Claude works rather than when the turn ends.
  // `last` is the running sum of the current turn's requests.
  let lastTurn = null
  const stepped = new Set()
  on('turn.step', async function* ($, e, next) {
    const r = yield* next(e)
    const u = r && r.usage
    if (u) {
      const step = {
        input: u.input_tokens || 0,
        output: u.output_tokens || 0,
        read: u.cache_read_input_tokens || 0,
        write: u.cache_creation_input_tokens || 0,
      }
      stepped.add(e.turnId)
      if (lastTurn !== e.turnId) {
        lastTurn = e.turnId
        last = { input: 0, output: 0, read: 0, write: 0 }
      }
      for (const key of Object.keys(step)) {
        last[key] += step[key]
        total[key] += step[key]
      }
      await refresh($)
      $.ui.invalidate('ui.render')
    }
    return r
  })

  // A turn whose steps reported nothing counts here, at its end, as before
  on('turn.complete', async ($, e, next) => {
    if (e.usage && !stepped.delete(e.turnId)) {
      last = {
        input: e.usage.input_tokens,
        output: e.usage.output_tokens,
        read: e.usage.cache_read_input_tokens,
        write: e.usage.cache_creation_input_tokens,
      }
      for (const key of Object.keys(last)) total[key] += last[key]
    }
    await refresh($)
    $.ui.invalidate('ui.render')
    return next(e)
  })

  // The footer row: one Text, so session, month and hit rate share one font, then the
  // triangle that opens the mods' band (pointing down) or closes it (pointing up)
  on('ui.render', { component: 'SessionMode' }, async ($, e, next) => {
    const rest = await next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    const open = await read($, barOpen)
    const toggle = Button({
      key: 'bar-toggle',
      label: open ? '▾' : '▴',
      onPress: async () => {
        await update($, barOpen, () => !open)
        await $.store.set('barOpen', !open)
      },
    })
    const hit = last ? ` · cache hit ${Math.round(rate(total) * 100)}%` : ''
    const line = `$${usd.toFixed(2)} session · $${month.usd.toFixed(2)} this month${month.since ? sinceLabel(month.since) : ''}${hit}`
    return Box({
      flexDirection: 'row',
      columnGap: 2,
      children: [...(rest ? [rest] : []), Text({ dimColor: true, children: [line] }), toggle],
    })
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const rest = await next(e)
    if (e.props.hasSurvey) return rest
    // Closed from the footer's triangle: the band draws nothing
    if (!(await read($, barOpen))) return rest
    const { Box, Text } = $.ui.resolve(e)
    if (!last) return rest
    const hit = rate(total)
    const tone = (r) => hex(mix(TEAL, NEON_GREEN, r))
    const costRow = [
      Box({ width: 5, flexShrink: 0, children: [Text({ dimColor: true, children: ['cost'] })] }),
      Text({ bold: true, children: [`$${usd.toFixed(2)}`] }),
      Text({ dimColor: true, children: [`in ${k(total.input)}  out ${k(total.output)}  read ${k(total.read)}  write ${k(total.write)}`] }),
      Text({ color: tone(hit), children: [`hit ${Math.round(hit * 100)}%`] }),
      Text({ color: tone(rate(last)), children: [`last ${Math.round(rate(last) * 100)}%`] }),
    ]

    return Box({
      flexDirection: 'column',
      children: [
        Box({ flexDirection: 'row', columnGap: 2, children: costRow }),
        ...(rest ? [rest] : []),
      ],
    })
  })
}
