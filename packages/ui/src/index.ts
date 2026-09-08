export const KAIRO_SPACES = [
  'command', 'today', 'projects', 'knowledge', 'mind', 'gantt', 'calendar', 'people',
  'research', 'automations', 'agents', 'computer', 'developer', 'crypto', 'finance',
  'home', 'analytics', 'maps', 'notifications', 'approvals', 'activity', 'models',
  'permissions', 'plugins', 'devices', 'system',
] as const

export type KairoSpace = (typeof KAIRO_SPACES)[number]
