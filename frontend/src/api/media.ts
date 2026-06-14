import { apiFetch } from './client'

export interface Media {
  id: number
  entry_id: number
  source_name: string
  date_added: string
  scrape_status: 'pending' | 'confirmed' | 'skipped'
  tmdb_id: number | null
  generated_files: string | null
  size: number | null
  metadata?: Record<string, string>
}

export interface Episode {
  season: number
  episode: number
  title: string | null
  aired: string | null
  plot: string | null
  rating: number | null
}

export const listMedia = (entryId: number) =>
  apiFetch<Media[]>(`/media/entry/${entryId}`)

export const listEpisodes = (mediaId: number) =>
  apiFetch<Episode[]>(`/media/${mediaId}/episodes`)
