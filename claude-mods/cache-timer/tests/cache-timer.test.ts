import { expect, mock, test } from 'claude-code/testing'

const BAND = {
  hasSurvey: false,
  isWorking: false,
  maxRows: 12,
  bodyColumns: 120,
  scroll: { offset: 0, bodyRows: 11 },
  view: {},
} as never

// The engine beneath the plugins: a turn ends with its answer, and an empty box is drawn.
function engine(on: any) {
  on('turn.complete', async (_$: unknown, e: { answer: string }) => ({ text: e.answer }))
  on('session.start', async () => ({}))
  on('ui.render', async ($: any, e: any) => $.ui.resolve(e).Box({ children: [] }))
  mock.env(on, { CLAUDE_CACHE_TTL_SECONDS: '3600' })
}

const turn = (extra: Record<string, unknown> = {}) =>
  ({ answer: 'ok', durationMs: 10, isAborted: false, turnId: 't1', ...extra }) as never

test("a subagent's request does not refresh the main conversation's cache", async ($, on) => {
  engine(on)
  mock.clock(on, { now: 2_000_000 })
  await $.turn.complete(turn({ agentId: 'sub-1' }))
  const band = await $.ui.mount({ plugin: 'cache-timer', surface: 'desktop', component: 'AbovePrompt', props: BAND })
  expect((await band.findAll({ type: 'Text', text: /left|cold/ })).length).toBe(0)
})

test('the countdown runs from that request on the session clock', async ($, on) => {
  engine(on)
  const clock = mock.clock(on, { now: 3_000_000 })
  await $.turn.complete(turn())
  await clock.advance(10 * 60 * 1000)
  const band = await $.ui.mount({ plugin: 'cache-timer', surface: 'desktop', component: 'AbovePrompt', props: BAND })
  const found = await band.findAll({ type: 'Text', text: /left/ })
  expect(found.length).toBe(1)
  expect(String((found[0] as { text?: string }).text)).toMatch(/50:00 left/)
})
