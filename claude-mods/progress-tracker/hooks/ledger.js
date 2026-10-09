// Desktop strips: each segment of a bar is one small SVG (so each can carry its own hover
// readout): a track that fills continuously, ending in a checkpoint that lights when the
// segment is done. Segments sit side by side, so a bar is always the same width however
// many steps it has. A segment draws an animation only while one is due (the fill growing,
// a checkpoint landing, a burst); otherwise its markup depends on the data alone, so a
// redraw with nothing new is the same image.

const hex = (n) => '#' + n.toString(16).padStart(6, '0')

export function mix(a, b, t) {
  const ch = (s) => Math.round(((a >> s) & 255) * (1 - t) + ((b >> s) & 255) * t)
  return (ch(16) << 16) | (ch(8) << 8) | ch(0)
}

export const TRACK = 0x3a3a46
export const GOLD = 0xffd166

const BAR = 6
const DOT = 3.6
const f2 = (n) => n.toFixed(2)

// A burst of sparks from (x, y): what a finished task or plan sets off.
function sparks(x, y, color, count, reach, delay = 0) {
  let out = ''
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2 + 0.35
    const dx = Math.cos(a) * reach
    const dy = Math.sin(a) * reach * 0.55
    out +=
      `<circle cx="${f2(x)}" cy="${f2(y)}" r="1.4" fill="${hex(i % 2 ? color : 0xffffff)}" ` +
      `style="--dx:${f2(dx)}px;--dy:${f2(dy)}px;animation:spark 900ms ${delay + i * 18}ms cubic-bezier(.15,.7,.3,1) both"/>`
  }
  return out
}

/**
 * One segment. opts: {
 *   width, height, fill (0..1), from (0..1, when the fill is growing), color,
 *   checkpoint: 'done' | 'focus' | 'open' | 'none',
 *   anim: null | 'step' | 'task' | 'plan',   // a checkpoint landing, a task or the plan finishing
 *   shimmer: boolean,                         // a light sweeping the track (task/plan finished)
 *   first, last                               // round the bar's outer ends
 * }
 */
export function segmentSvg(o) {
  const W = o.width
  const H = o.height
  const cy = H / 2
  const hasDot = o.checkpoint !== 'none'
  const dotX = W - DOT - 2
  const x0 = o.first ? 1 : 0
  const x1 = hasDot ? dotX - DOT - 2 : W - (o.last ? 1 : 0)
  const trackW = Math.max(0, x1 - x0)
  const color = o.anim === 'plan' ? GOLD : o.color
  const fill = Math.max(0, Math.min(1, o.fill))
  const fillW = trackW * fill
  const r = o.first || o.last ? 3 : 1.2
  const css = []
  const defs = []
  let body = ''

  body += `<rect x="${f2(x0)}" y="${f2(cy - BAR / 2)}" width="${f2(trackW)}" height="${BAR}" rx="${r}" fill="${hex(TRACK)}"/>`
  if (fillW > 0.3) {
    const growing = o.from != null && Math.abs(o.from - fill) > 0.001 && fill > 0
    const start = growing ? Math.max(0, Math.min(1, o.from / fill)) : 1
    if (growing) css.push(`.f{transform-origin:${f2(x0)}px 50%;animation:grow 800ms cubic-bezier(.2,.8,.2,1) both}@keyframes grow{from{transform:scaleX(${f2(start)})}}`)
    defs.push(
      `<linearGradient id="lg" x1="0" x2="1"><stop offset="0" stop-color="${hex(mix(color, 0x000000, 0.25))}"/><stop offset="1" stop-color="${hex(color)}"/></linearGradient>`,
      `<filter id="gl" x="-20%" y="-200%" width="140%" height="500%"><feGaussianBlur stdDeviation="1.6"/></filter>`,
    )
    body +=
      `<g class="f"><rect x="${f2(x0)}" y="${f2(cy - BAR / 2)}" width="${f2(fillW)}" height="${BAR}" rx="${r}" fill="${hex(color)}" filter="url(#gl)" opacity="0.6"/>` +
      `<rect x="${f2(x0)}" y="${f2(cy - BAR / 2)}" width="${f2(fillW)}" height="${BAR}" rx="${r}" fill="url(#lg)"/>` +
      // A bright head on a fill that is still going, so partial progress reads as alive
      (fill < 1 ? `<rect x="${f2(x0 + fillW - 1.6)}" y="${f2(cy - BAR / 2)}" width="1.6" height="${BAR}" fill="${hex(mix(color, 0xffffff, 0.55))}"/>` : '') +
      `</g>`
  }

  if (o.shimmer && trackW > 0) {
    css.push(`.sh{animation:sweep 1100ms 120ms ease-in-out 2 both}@keyframes sweep{from{transform:translateX(${f2(-trackW * 0.4)}px)}to{transform:translateX(${f2(trackW * 1.1)}px)}}`)
    defs.push(
      `<linearGradient id="sg" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>`,
      `<clipPath id="tc"><rect x="${f2(x0)}" y="${f2(cy - BAR / 2)}" width="${f2(trackW)}" height="${BAR}" rx="${r}"/></clipPath>`,
    )
    body += `<g clip-path="url(#tc)"><rect class="sh" x="${f2(x0)}" y="${f2(cy - BAR / 2)}" width="${f2(trackW * 0.35)}" height="${BAR}" fill="url(#sg)"/></g>`
  }

  if (hasDot) {
    const done = o.checkpoint === 'done'
    const focus = o.checkpoint === 'focus'
    const stroke = focus ? hex(mix(o.color, 0xffffff, 0.45)) : done ? hex(mix(color, 0xffffff, 0.3)) : hex(mix(TRACK, 0xffffff, 0.12))
    // A diamond: the checkpoint
    const d = `M${f2(dotX)} ${f2(cy - DOT)} L${f2(dotX + DOT)} ${f2(cy)} L${f2(dotX)} ${f2(cy + DOT)} L${f2(dotX - DOT)} ${f2(cy)} Z`
    if (done) {
      defs.push(`<filter id="dg" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="1.8"/></filter>`)
      body += `<path d="${d}" fill="${hex(color)}" filter="url(#dg)" opacity="0.8"/>`
    }
    body += `<path class="cp" d="${d}" fill="${done ? hex(color) : hex(TRACK)}" stroke="${stroke}" stroke-width="1"/>`
    if (focus) {
      css.push(`.fo{transform-box:fill-box;transform-origin:center;animation:breathe 2.4s ease-in-out infinite}@keyframes breathe{50%{opacity:.35;transform:scale(1.35)}}`)
      body += `<path class="fo" d="${d}" fill="none" stroke="${hex(mix(o.color, 0xffffff, 0.45))}" stroke-width="0.8"/>`
    }
    if (o.anim) {
      const big = o.anim !== 'step'
      // The checkpoint lands: it pops, and a ring spreads out from it
      css.push(
        `.cp{transform-box:fill-box;transform-origin:center;animation:pop ${big ? 700 : 520}ms cubic-bezier(.3,1.6,.5,1) both}` +
          `@keyframes pop{0%{transform:scale(.3) rotate(-45deg)}60%{transform:scale(${big ? 1.9 : 1.5}) rotate(8deg)}100%{transform:scale(1)}}` +
          `.rg{transform-box:fill-box;transform-origin:center;animation:ring ${big ? 1000 : 800}ms ease-out ${big ? 3 : 1} both}` +
          `@keyframes ring{from{transform:scale(.6);opacity:.95}to{transform:scale(${big ? 3.4 : 2.6});opacity:0}}`,
      )
      body += `<circle class="rg" cx="${f2(dotX)}" cy="${f2(cy)}" r="${DOT + 0.6}" fill="none" stroke="${hex(mix(color, 0xffffff, 0.4))}" stroke-width="1.2"/>`
      if (big) {
        css.push(`@keyframes spark{0%{opacity:1;transform:translate(0,0) scale(1.2)}100%{opacity:0;transform:translate(var(--dx),var(--dy)) scale(.4)}}`)
        body += sparks(dotX, cy, color, o.anim === 'plan' ? 14 : 9, o.anim === 'plan' ? 15 : 11)
        if (o.anim === 'plan') body += sparks(dotX, cy, GOLD, 10, 9, 260)
      }
    }
  }

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${f2(W)}" height="${H}" viewBox="0 0 ${f2(W)} ${H}" overflow="visible">` +
    (css.length ? `<style>@media (prefers-reduced-motion: reduce){*{animation:none!important}}${css.join('')}</style>` : '') +
    (defs.length ? `<defs>${defs.join('')}</defs>` : '') +
    body +
    `</svg>`
  )
}

// Terminal: one row of cells. segs: [{ cols, fill, checkpoint, color }]; a segment's last
// column is its checkpoint (◆ done, ◈ focus, ◇ open), the others fill left to right.
export function terminalCells(segs, defaultColor) {
  const numbers = []
  for (const s of segs) {
    const track = s.checkpoint === 'none' ? s.cols : s.cols - 1
    const lit = s.fill * track
    for (let c = 0; c < track; c++) {
      const on = c + 1 <= lit + 0.001
      const half = !on && c < lit
      numbers.push(on ? 0x2501 : half ? 0x257a : 0x2500, on || half ? s.color : TRACK, defaultColor)
    }
    if (s.checkpoint !== 'none') {
      const glyph = s.checkpoint === 'done' ? 0x25c6 : s.checkpoint === 'focus' ? 0x25c8 : 0x25c7
      numbers.push(glyph, s.checkpoint === 'open' ? mix(TRACK, 0xffffff, 0.25) : s.color, defaultColor)
    }
  }
  return new Uint8Array(Uint32Array.from(numbers).buffer).toBase64()
}
