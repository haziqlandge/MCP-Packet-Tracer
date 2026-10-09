import { expect, test } from 'claude-code/testing'
import { shortName } from '../hooks/parse-plan.js'

const BAND = {
  hasSurvey: false,
  isWorking: false,
  maxRows: 12,
  bodyColumns: 120,
  scroll: { offset: 0, bodyRows: 11 },
  view: {},
} as never

function engine(on: any) {
  on('tool.call', async () => ({ result: 'ok' }))
  on('ui.render', async ($: any, e: any) => $.ui.resolve(e).Box({ children: [] }))
}

test('a todo list draws one cell per todo and names the one in progress', async ($, on) => {
  engine(on)
  await $.tool.call({
    tool: 'TodoWrite',
    input: {
      todos: [
        { content: 'Parse the plan', status: 'completed', activeForm: 'Parsing' },
        { content: 'Draw the strips', status: 'in_progress', activeForm: 'Drawing' },
        { content: 'Sync the mods', status: 'pending', activeForm: 'Syncing' },
      ],
    },
  } as never)
  const band = await $.ui.mount({ plugin: 'progress-tracker', surface: 'desktop', component: 'AbovePrompt', props: BAND })
  expect((await band.findAll({ type: 'Svg' })).length).toBe(6)
  // The label is the name alone; the count waits in its hover readout
  expect((await band.findAll({ type: 'Text', text: /^Draw the strips$/ })).length).toBe(1)
  expect((await band.findAll({ type: 'Text', text: /1\/3\s+Draw the strips/ })).length).toBe(1)
})

test('both bars take 70% of the band however many steps there are', async ($, on) => {
  engine(on)
  for (const count of [2, 5]) {
    const list = Array.from({ length: count }, (_, i) => ({ content: `Step ${i}`, status: i === 0 ? 'in_progress' : 'pending', activeForm: 'x' }))
    await $.tool.call({ tool: 'TodoWrite', input: { todos: list } } as never)
    const band = await $.ui.mount({ plugin: 'progress-tracker', surface: 'desktop', component: 'AbovePrompt', props: BAND })
    const svgs = (await band.findAll({ type: 'Svg' })) as any[]
    const widths = svgs.map((s) => s.props?.width ?? 0)
    const half = widths.slice(0, count).reduce((a, b) => a + b, 0)
    expect(svgs.length).toBe(count * 2)
    // 70% of 120 cells, 8 CSS px a cell
    expect(Math.round(half)).toBe(672)
  }
})

test('a long name shows at most five words; the whole of it waits behind a hover', async ($, on) => {
  engine(on)
  const title = 'Write the hover readout for long names that never fit'
  await $.tool.call({ tool: 'TodoWrite', input: { todos: [{ content: title, status: 'in_progress', activeForm: 'x' }] } } as never)
  const band = await $.ui.mount({ plugin: 'progress-tracker', surface: 'desktop', component: 'AbovePrompt', props: BAND })
  const short = (await band.findAll({ type: 'Text', text: /^Write the hover readout for…$/ })) as any[]
  expect(short.length).toBe(1)
  // The full text is drawn only in readouts hidden until hovered: the label's, and one per
  // segment (a todo list's one todo is a segment of both bars)
  expect((await band.findAll({ type: 'Text', text: /never fit/ })).length).toBe(3)
})

test('shortName keeps whole words, at most five, within the room given', async () => {
  expect(shortName('Remove server-error models')).toBe('Remove server-error models')
  expect(shortName('Visual language: clean, not cluttered at all')).toBe('Visual language: clean, not cluttered…')
  expect(shortName('One zoom view with arrows', 12)).toBe('One zoom…')
  expect(shortName('Supercalifragilistic name', 4)).toBe('Supercalifragilistic…')
})
