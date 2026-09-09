import { apiJson } from './api'

export type CalendarSourceRecord = {
  id: string
  key: string
  provider: string
  external_account_ref: string
  display_name: string
  status: string
  metadata_json: Record<string, unknown>
  last_sync_at?: string | null
  last_error?: string | null
  created_at: string
  updated_at: string
}

export type ExternalCalendarEventRecord = {
  id: string
  source_id: string
  source_key: string
  source_provider: string
  source_display_name: string
  external_id: string
  title: string
  start_at: string
  end_at: string
  all_day: boolean
  status: string
  location?: string | null
  source_url?: string | null
  metadata: Record<string, unknown>
  source_updated_at?: string | null
  observed_at: string
}

export function fetchCalendarSources(): Promise<CalendarSourceRecord[]> {
  return apiJson('/v1/calendar/sources')
}

export function fetchExternalCalendarEvents(
  start: Date,
  end: Date,
  sourceId?: string,
): Promise<ExternalCalendarEventRecord[]> {
  const params = new URLSearchParams({
    start: start.toISOString(),
    end: end.toISOString(),
  })
  if (sourceId) params.set('source_id', sourceId)
  return apiJson(`/v1/calendar/external-events?${params.toString()}`)
}
