function knowledgeErrorMessage(body: any) {
  const detail = body?.detail
  return typeof detail === 'string' ? detail : detail?.message
}

export async function readKnowledgeJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const message = knowledgeErrorMessage(body)
    throw new Error(message || `KAIRO Core répond ${response.status}`)
  }
  return body as T
}

export async function readKnowledgeHttpError(
  response: Response,
  fallbackMessage: string,
): Promise<Error> {
  const body = await response.json().catch(() => null)
  const message = knowledgeErrorMessage(body)
  return new Error(message || fallbackMessage)
}
