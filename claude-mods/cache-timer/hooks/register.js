import { atom, read, update } from 'claude-code'

const WIDTH = 26
const DEFAULT_TTL_SECONDS = 3600
const DEFAULT_COLOR = 0x01000000
const TRACK = 0x34343e
const NEON_GREEN = 0xc4e04a
const NEON_CAP = 0xf0ffd6
const TEAL = 0x16c9b4
const TEAL_CAP = 0xd2fff8

// When this session's main conversation last called the model; that request
// refreshed its cache. Kept in session state, not a module variable: every
// session watching this folder reloads the module on any save in it, and a
// reload wipes module variables, so each session's countdown restarted at once.
const lastTouch = atom({ plugin: 'cache-timer', key: 'lastTouch' }, null)

// A subagent's requests carry its own prefix and warm its own cache, not this
// conversation's, so only main-loop events (no agentId) count.
async function touch($, e) {
  if (e.agentId) return
  const now = await $.clock.now()
  await update($, lastTouch, () => now)
}

// The band's open/closed switch, owned by cost-ticker; while closed this mod draws nothing
const barOpen = atom({ plugin: 'cost-ticker', key: 'barOpen' }, true)

function mix(a, b, t) {
  const ch = (s) => Math.round(((a >> s) & 255) * (1 - t) + ((b >> s) & 255) * t)
  return (ch(16) << 16) | (ch(8) << 8) | ch(0)
}

function cellsOf(fraction, color, cap) {
  const filled = Math.round(Math.max(0, Math.min(1, fraction)) * WIDTH)
  const ramp = ['·', '░', '▒', '▓', '█']
  const numbers = []
  for (let i = 0; i < WIDTH; i++) {
    let char, fg
    if (i >= filled) {
      char = '░'
      fg = TRACK
    } else if (i === filled - 1) {
      char = '█'
      fg = cap
    } else {
      const t = filled > 1 ? i / (filled - 1) : 1
      char = ramp[Math.min(ramp.length - 1, Math.floor(t * ramp.length))]
      fg = mix(TRACK, color, 0.2 + 0.8 * t)
    }
    numbers.push(char.codePointAt(0), fg, DEFAULT_COLOR)
  }
  return new Uint8Array(Uint32Array.from(numbers).buffer).toBase64()
}


// Desktop bar: a grid of square tiles. The lit tiles run from the left, brightest at the head and
// fading toward the end of the lit run; the run shrinks smoothly from the right as the cache cools.
function svgBar(fraction, color) {
  const COLS = 36
  const ROWS = 2
  const PITCH = 8.4
  const TILE = 7.2
  const W = COLS * PITCH + 2
  const H = ROWS * PITCH + 2
  const f = Math.max(0, Math.min(1, fraction))
  const lit = f * COLS
  const hex = (n) => '#' + n.toString(16).padStart(6, '0')
  const tiles = []
  for (let c = 0; c < COLS; c++) {
    // 1 for a fully lit column, a fraction for the one being consumed, 0 for a spent one
    const on = Math.max(0, Math.min(1, lit - c))
    for (let r = 0; r < ROWS; r++) {
      const noise = (((c * 7919 + r * 104729 + 17) % 23) / 23 - 0.5) * 0.3
      const fade = lit > 1 ? 0.3 + 0.7 * (c / lit) : 1
      let level = on * Math.max(0.08, Math.min(1, fade + noise))
      let fill = mix(0x26262b, color, level)
      // A few bright sparkle tiles, as in the reference
      if (on > 0.99 && (c * 5 + r * 3) % 29 === 0) fill = mix(fill, 0xffffff, 0.45)
      const x = 1 + c * PITCH + (PITCH - TILE) / 2
      const y = 1 + r * PITCH + (PITCH - TILE) / 2
      tiles.push(`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${TILE}" height="${TILE}" rx="1" fill="${hex(fill)}"/>`)
    }
  }
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W.toFixed(0)}" height="${H.toFixed(0)}" viewBox="0 0 ${W.toFixed(1)} ${H.toFixed(1)}">` +
    `<rect width="${W.toFixed(1)}" height="${H.toFixed(1)}" rx="4" fill="#1a1a1e"/>` +
    tiles.join('') +
    `</svg>`
  )
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    $.clock.every(1000, async () => {
      if (await read($, lastTouch)) $.ui.invalidate('ui.render')
    })
    return next(e)
  })

  on('turn.step', async function* ($, e, next) {
    await touch($, e)
    return yield* next(e)
  })

  on('turn.complete', async ($, e, next) => {
    await touch($, e)
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const rest = await next(e)
    const touched = await read($, lastTouch)
    if (!touched || !(await read($, barOpen))) return rest
    const { Box, Text, Raster, Svg } = $.ui.resolve(e)

    // CLAUDE_CACHE_TTL_SECONDS: 3600 = 1-hour (subscription within plan usage), 300 = 5-minute (API key or usage credits)
    const ttl = Number(await $.env.get('CLAUDE_CACHE_TTL_SECONDS')) || DEFAULT_TTL_SECONDS
    const left = Math.max(0, ttl - ((await $.clock.now()) - touched) / 1000)
    const warmth = left / ttl

    // Neon green while warm, easing to teal as the cache nears cold
    const heat = warmth
    const color = mix(TEAL, NEON_GREEN, heat)
    const cap = mix(TEAL_CAP, NEON_CAP, heat)
    const mm = Math.floor(left / 60)
    const ss = String(Math.floor(left % 60)).padStart(2, '0')
    const state = left === 0 ? 'cold' : warmth > 0.5 ? 'warm' : warmth > 0.15 ? 'cooling' : 'going cold'
    const text = left === 0 ? 'cold: next prompt re-reads everything' : `${state}  ${mm}:${ss} left`

    const bar =
      e.surface === 'terminal'
        ? Raster({ key: 'cache', columns: WIDTH, rows: 1, cells: cellsOf(warmth, color, cap) })
        : e.surface === 'desktop'
          ? Svg({ source: svgBar(warmth, color), alt: `Cache ${Math.round(warmth * 100)}% warm`, width: 304, height: 19 })
          : Text({ color: warmth > 0.5 ? 'green' : 'cyan', children: ['█'.repeat(Math.round(warmth * WIDTH)) + '░'.repeat(WIDTH - Math.round(warmth * WIDTH))] })

    return Box({
      flexDirection: 'column',
      children: [
        Box({
          flexDirection: 'row',
          columnGap: 1,
          children: [Box({ width: 5, flexShrink: 0, children: [Text({ dimColor: true, children: ['cache'] })] }), bar, Text({ children: [text] })],
        }),
        ...(rest ? [rest] : []),
      ],
    })
  })
}
