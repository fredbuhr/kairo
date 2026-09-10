import { useState } from 'react'

import KnowledgeSearchPanel from './KnowledgeSearchPanel'
import KnowledgeWorkspace, { type KnowledgeInspectionTarget } from './KnowledgeWorkspace'

type Props = {
  apiUrl: string
}

export default function KnowledgePanel({ apiUrl }: Props) {
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const [inspectionTarget, setInspectionTarget] = useState<KnowledgeInspectionTarget | null>(null)

  return (
    <>
      <KnowledgeSearchPanel
        apiUrl={apiUrl}
        onInspectResult={(target) => {
          setSelectedDocumentId(target.documentId)
          setInspectionTarget(target)
        }}
      />
      <KnowledgeWorkspace
        apiUrl={apiUrl}
        selectedDocumentId={selectedDocumentId}
        onSelectedDocumentIdChange={setSelectedDocumentId}
        inspectionTarget={inspectionTarget}
      />
    </>
  )
}
