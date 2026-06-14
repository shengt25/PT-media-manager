import { apiFetch } from './client'

export interface ScanAddItem {
  source_name: string
  video_stem: string | null
}

export interface ScanResultItem {
  entry_id: number
  entry_name: string
  added: ScanAddItem[]
  removed: { id: number; source_name: string }[]
  auto_removed: string[]
  notes: string[]
}

export const runScan = () => apiFetch<ScanResultItem[]>('/scan/', { method: 'POST' })

export const confirmAdd = (entryId: number, sourceName: string, videoStem: string | null) =>
  apiFetch<void>('/scan/confirm-add', {
    method: 'POST',
    body: JSON.stringify({ entry_id: entryId, source_name: sourceName, video_stem: videoStem }),
  })

export const confirmRemove = (mediaId: number) =>
  apiFetch<void>('/scan/confirm-remove', {
    method: 'POST',
    body: JSON.stringify({ media_id: mediaId }),
  })
