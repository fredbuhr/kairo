export type CanonicalDocument = {
  id: string
  asset_id: string
  project_id: string
  title: string
  media_type?: string | null
  source_sha256?: string | null
  status: string
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type DocumentVersion = {
  id: string
  document_id: string
  generation: number
  task_id?: string | null
  parser: string
  parser_version?: string | null
  source_sha256?: string | null
  status: string
  chunk_count: number
  metadata_json: Record<string, unknown>
  last_error?: string | null
  created_at: string
  completed_at?: string | null
}

export type DocumentChunk = {
  id: string
  document_version_id: string
  ordinal: number
  text: string
  content_sha256: string
  metadata_json: Record<string, unknown>
  created_at: string
}

export type KnowledgeInspectionTarget = {
  documentId: string
  documentVersionId: string
  chunkId: string
  ordinal: number
}

export type KnowledgeChunkWindow = {
  project_id: string
  document_id: string
  document_version_id: string
  anchor_chunk_id: string
  offset: number
  total: number
  chunks: DocumentChunk[]
}

export type AssetUpload = {
  id: string
}

export type DocumentImportRun = {
  document: CanonicalDocument
  version: DocumentVersion
}

export type KnowledgeSearchResult = {
  document_id: string
  document_project_id: string
  document_title: string
  document_version_id: string
  generation: number
  chunk_id: string
  ordinal: number
  excerpt: string
  content_sha256: string
  rank: number
}
