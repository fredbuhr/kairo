import { getAccessToken } from './authSession'

/**
 * Nevolium-owned fetch boundary for public Core APIs.
 *
 * S2 deliberately only centralizes bearer injection. Error decoding, retries,
 * typed endpoint helpers and per-workspace adapters remain separate concerns.
 */
export async function nevoliumFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const token = await getAccessToken()
  const headers = new Headers(init.headers || {})

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  return fetch(input, {
    ...init,
    headers,
  })
}
