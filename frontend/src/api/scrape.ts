import { apiFetch } from './client'

export interface TmdbCandidate {
  tmdb_id: number
  title: string
  year: string | null
  overview: string | null
  rating: number | null
  poster_path: string | null
}


export const getPoster = (tmdbId: number, mediaType: string, language: string) =>
  apiFetch<{ poster_path: string | null }>(`/scrape/poster?tmdb_id=${tmdbId}&media_type=${mediaType}&language=${language}`)

export const searchScrape = (mediaId: number, query: string, year?: number, language = 'zh-CN') =>
  apiFetch<TmdbCandidate[]>(`/scrape/${mediaId}/search`, {
    method: 'POST',
    body: JSON.stringify({ query, year, language }),
  })

export const confirmScrape = (mediaId: number, tmdbId: number, language = 'zh-CN', imageLanguage?: string) =>
  apiFetch<void>(`/scrape/${mediaId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ tmdb_id: tmdbId, language, image_language: imageLanguage }),
  })

export const rescrape = (mediaId: number, tmdbId: number, language = 'zh-CN', imageLanguage?: string) =>
  apiFetch<void>(`/scrape/${mediaId}/rescrape`, {
    method: 'POST',
    body: JSON.stringify({ tmdb_id: tmdbId, language, image_language: imageLanguage }),
  })

export const syncEpisodes = (mediaId: number) =>
  apiFetch<{ added: number; generated: number; warnings: string[] }>(`/scrape/${mediaId}/sync-episodes`, { method: 'POST' })
