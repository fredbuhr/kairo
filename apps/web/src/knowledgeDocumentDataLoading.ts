import { useEffect, useState } from 'react'

import type { CanonicalDocument, DocumentVersion } from './knowledgeTypes'
import { usePagedCollection } from './lib/usePagedCollection'

export function useKnowledgeDocumentDataLoading({ apiUrl, projectId, documentId, versionId }: {
  apiUrl: string; projectId: string; documentId: string; versionId?: string | null
}) {
  const documentPage = usePagedCollection<CanonicalDocument>(
    projectId ? `${apiUrl}/v1/documents?project_id=${encodeURIComponent(projectId)}` : null,
    projectId && documentId ? `${apiUrl}/v1/documents/${documentId}` : null,
  )
  const versionPage = usePagedCollection<DocumentVersion>(
    documentId ? `${apiUrl}/v1/documents/${documentId}/versions` : null,
    documentId && versionId ? `${apiUrl}/v1/document-versions/${versionId}` : null,
  )
  const [versionsDocumentId, setVersionsDocumentId] = useState<string | null>(null)
  useEffect(() => {
    setVersionsDocumentId(versionPage.loading ? null : documentId || null)
  }, [documentId, versionPage.loading])
  return { documentPage, versionPage, versionsDocumentId, setVersionsDocumentId }
}
