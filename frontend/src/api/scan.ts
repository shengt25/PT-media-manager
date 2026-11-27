import { apiFetch } from './client'

export interface ScanAddItem {
  source_path: string
}

export interface ScanResultItem {
  entry_id: number
  entry_name: string
  added: ScanAddItem[]
  removed: { id: number; source_name: string }[]
  episode_updates: { media_id: number; source_name: string; files: string[] }[]
  auto_removed: string[]
  notes: string[]
}

export const runScan = () => apiFetch<ScanResultItem[]>('/scan/', { method: 'POST' })

export const confirmAdd = (entryId: number, sourcePath: string) =>
  apiFetch<void>('/scan/confirm-add', {
    method: 'POST',
    body: JSON.stringify({ entry_id: entryId, source_path: sourcePath }),
  })

export const confirmRemove = (mediaId: number) =>
  apiFetch<void>('/scan/confirm-remove', {
    method: 'POST',
    body: JSON.stringify({ media_id: mediaId }),
  })

export const confirmEpisodeUpdates = (mediaId: number, files: string[]) =>
  apiFetch<{ linked: number; existing: number }>('/scan/confirm-episode-updates', {
    method: 'POST',
    body: JSON.stringify({ media_id: mediaId, files }),
  })
