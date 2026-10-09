import { expect, mock, test } from 'claude-code/testing'

// The engine beneath the plugin: one store shared by every session, this session's
// id and running cost, and an empty footer.
function engine(on: any, store: Map<string, unknown>, cost: { usd: number }) {
  on('store.get', async (_$: unknown, e: { key: string }) => ({ value: store.get(e.key) }))
  on('store.set', async (_$: unknown, e: { key: string; value: unknown }) => {
    store.set(e.key, JSON.parse(JSON.stringify(e.value)))
    return { value: undefined }
  })
  on('store.keys', async () => ({ value: [...store.keys()] }))
  on('session.id', async () => ({ value: 'me' }))
  on('session.usage', async () => ({ value: { startedAt: 0, context: {}, rateLimits: [], cost: { usd: cost.usd } } }))
  on('session.start', async () => ({}))
  on('turn.complete', async (_$: unknown, e: { answer: string }) => ({ text: e.answer }))
  on('ui.render', async ($: any, e: any) => $.ui.resolve(e).Box({ children: [] }))
  mock.clock(on, { now: Date.parse('2026-10-03T12:00:00Z') })
}

const turn = () =>
  ({
    answer: 'ok',
    durationMs: 10,
    isAborted: false,
    turnId: 't1',
    usage: { input_tokens: 10, output_tokens: 5, cache_read_input_tokens: 90, cache_creation_input_tokens: 0 },
  }) as never

async function footer($: any) {
  const row = await $.ui.mount({ plugin: 'cost-ticker', surface: 'desktop', component: 'SessionMode', props: { modes: [] } })
  const found = await row.findAll({ type: 'Text', text: /this month/ })
  expect(found.length).toBe(1)
  return String((found[0] as { text?: string }).text)
}

test("the month sums every session's spend this month, in one line", async ($, on) => {
  const store = new Map<string, unknown>([
    ['since', '2026-10-03'],
    ['m:2026-09:other', { spent: 40, last: 40 }],
    ['m:2026-10:other', { spent: 12.5, last: 52.5 }],
  ])
  const cost = { usd: 5 }
  engine(on, store, cost)

  await $.turn.complete(turn())
  expect(await footer($)).toBe('$5.00 session · $17.50 this month (since 3 Oct) · cache hit 90%')

  cost.usd = 8
  await $.turn.complete(turn())
  expect(await footer($)).toMatch(/^\$8\.00 session · \$20\.50 this month/)

  // A resumed session's cost restarts from zero in the engine; the session figure carries on
  cost.usd = 2
  await $.turn.complete(turn())
  expect(await footer($)).toMatch(/^\$10\.00 session · \$22\.50 this month/)
})

test("a session carried over from last month counts only this month's share", async ($, on) => {
  const store = new Map<string, unknown>([
    ['since', '2026-09-01'],
    ['m:2026-09:me', { spent: 30, last: 30 }],
  ])
  const cost = { usd: 34 }
  engine(on, store, cost)
  await $.turn.complete(turn())
  expect(await footer($)).toBe('$34.00 session · $4.00 this month · cache hit 90%')
})

const BAND = {
  hasSurvey: false,
  isWorking: false,
  maxRows: 12,
  bodyColumns: 120,
  scroll: { offset: 0, bodyRows: 11 },
  view: {},
} as never

test('the footer triangle points down while the band is open, up once pressed, and is remembered', async ($, on) => {
  const store = new Map<string, unknown>()
  engine(on, store, { usd: 1 })
  await $.turn.complete(turn())
  const mount = (component: string, props: unknown) =>
    $.ui.mount({ plugin: 'cost-ticker', surface: 'desktop', component, props } as never)
  const lines = async (band: any) => (await band.findAll({ type: 'Text', text: /^cost/ })).length

  const footer = await mount('SessionMode', { modes: [] })
  expect((await footer.find({ key: 'bar-toggle' })).props.label).toBe('▾')
  expect(await lines(await mount('AbovePrompt', BAND))).toBe(1)

  await footer.press({ key: 'bar-toggle' })
  expect((await (await mount('SessionMode', { modes: [] })).find({ key: 'bar-toggle' })).props.label).toBe('▴')
  expect(await lines(await mount('AbovePrompt', BAND))).toBe(0)
  expect(store.get('barOpen')).toBe(false)
})

test('a session that predates the ledger starts from what the month records hold for it', async ($, on) => {
  // This session spent $30 in an earlier process (recorded last at $30), and this process is at $1
  const store = new Map<string, unknown>([
    ['since', '2026-10-01'],
    ['m:2026-10:me', { spent: 30, last: 30 }],
  ])
  const cost = { usd: 1 }
  engine(on, store, cost)
  await $.turn.complete(turn())
  expect(await footer($)).toMatch(/^\$31\.00 session · \$31\.00 this month/)
  cost.usd = 4
  await $.turn.complete(turn())
  expect(await footer($)).toMatch(/^\$34\.00 session · \$34\.00 this month/)
})
