import { apiFetch } from './client'

export interface Entry {
  id: number
  name: string
  source_path: string
  link_path: string
  media_type: 'movie' | 'tv'
}

export interface EntryCreate {
  name: string
  source_path: string
  link_path: string
  media_type: 'movie' | 'tv'
}

export interface EntryUpdate {
  name?: string
  source_path?: string
  link_path?: string
  media_type?: 'movie' | 'tv'
}

export const listEntries = () => apiFetch<Entry[]>('/entries/')

export const createEntry = (data: EntryCreate) =>
  apiFetch<Entry>('/entries/', { method: 'POST', body: JSON.stringify(data) })

export const updateEntry = (id: number, data: EntryUpdate) =>
  apiFetch<Entry>(`/entries/${id}`, { method: 'PATCH', body: JSON.stringify(data) })

export const deleteEntry = (id: number) =>
  apiFetch<void>(`/entries/${id}`, { method: 'DELETE' })
