import { apiFetch } from './client'

export interface Media {
  id: number
  entry_id: number
  source_name: string
  date_added: string
  scrape_status: 'pending' | 'confirmed' | 'partial'
  tmdb_id: number | null
  generated_files: string | null
  size: number | null
  scrape_language: string | null
  image_language: string | null
  scrape_detail: string | null
  incomplete: boolean
  metadata?: Record<string, string>
}

export interface Episode {
  file: string
  season: number | null
  episode: number | null
  status: 'matched' | 'no_tmdb_data' | 'unidentified'
  title: string | null
  aired: string | null
}

export const listMedia = (entryId: number) =>
  apiFetch<Media[]>(`/media/entry/${entryId}`)

export const listEpisodes = (mediaId: number) =>
  apiFetch<Episode[]>(`/media/${mediaId}/episodes`)
