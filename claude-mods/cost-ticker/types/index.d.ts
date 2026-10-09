/** Whether the mods' band above the prompt is open; cost-ticker owns it, every mod in the band reads it. */
export type BarOpen = boolean

declare module 'claude-code' {
  interface PluginState {
    'cost-ticker': { barOpen: BarOpen }
  }
}
