/** When this session's main conversation last called the model, in ms; null before the first call. */
export type Touch = number | null

declare module 'claude-code' {
  interface PluginState {
    'cache-timer': { lastTouch: Touch }
  }
}
