import { apiFetch } from './client'

export interface AppSettings {
  id: number
  tmdb_proxy: string | null
}

export const getSettings = () => apiFetch<AppSettings>('/settings/')

export const updateSettings = (tmdbProxy: string | null) =>
  apiFetch<AppSettings>('/settings/', {
    method: 'PUT',
    body: JSON.stringify({ tmdb_proxy: tmdbProxy }),
  })
