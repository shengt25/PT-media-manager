import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react'
import { type Entry } from '@/api/entries'
import { type Media } from '@/api/media'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

interface Props {
  entries: Entry[]
  mediaMap: Map<number, Media[]>
  selectedId: number | null
  onSelect: (media: Media, entry: Entry) => void
}

function statusLabel(status: Media['scrape_status']) {
  if (status === 'pending') return 'Unscraped'
  if (status === 'partial') return 'Partial'
  return ''
}

function statusClassName(status: Media['scrape_status']) {
  if (status === 'pending') return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300'
  if (status === 'partial') return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-300'
  return ''
}

function sortMedia(list: Media[]) {
  return [...list].sort((a, b) => {
    const statusWeight = (media: Media) => {
      if (media.scrape_status === 'pending') return 0
      if (media.scrape_status === 'partial') return 1
      return 2
    }
    const byStatus = statusWeight(a) - statusWeight(b)
    if (byStatus !== 0) return byStatus
    return a.source_name.localeCompare(b.source_name)
  })
}

function MediaCard({ media, selected, onClick }: { media: Media; selected: boolean; onClick: () => void }) {
  const [posterError, setPosterError] = useState(false)
  const displayName = media.source_name
  const metadata = (media as Media & { metadata?: Record<string, string> }).metadata

  const title = metadata?.title
  const year = metadata?.year
  const label = title ? `${title}${year ? ` (${year})` : ''}` : displayName
  const isScraped = media.scrape_status === 'confirmed' || media.scrape_status === 'partial'
  const hasPoster = isScraped && !posterError

  return (
    <button
      onClick={onClick}
      className={cn(
        'group w-full overflow-hidden rounded-lg border bg-card text-left shadow-sm transition-colors',
        selected ? 'border-primary ring-2 ring-ring/25' : 'border-border hover:border-ring/60'
      )}
    >
      <div className="relative aspect-[2/3] bg-muted">
        {hasPoster ? (
          <img
            src={`${API_BASE}/media/${media.id}/thumb`}
            alt=""
            className="size-full object-cover"
            onError={() => setPosterError(true)}
          />
        ) : (
          <div className="flex size-full items-center justify-center bg-muted px-2">
            <span className="line-clamp-4 break-words text-center text-xs font-medium leading-snug text-muted-foreground">
              {displayName}
            </span>
          </div>
        )}
        {media.scrape_status !== 'confirmed' && (
          <Badge
            variant="outline"
            className={cn('absolute left-2 top-2 h-5 max-w-[calc(100%-1rem)] rounded-md px-1.5', statusClassName(media.scrape_status))}
          >
            {statusLabel(media.scrape_status)}
          </Badge>
        )}
        {media.incomplete && (
          <div
            className="absolute right-2 top-2 flex size-5 items-center justify-center rounded-full border border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300"
            title="Some files are missing TMDB data"
          >
            <AlertTriangle className="size-3" />
          </div>
        )}
      </div>
      <div className="min-h-20 p-2.5">
        <p
          className={cn(
            'text-sm font-medium',
            isScraped
              ? 'line-clamp-2 leading-snug'
              : 'line-clamp-3 break-all leading-normal'
          )}
        >
          {label}
        </p>
        {!isScraped && title && (
          <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{displayName}</p>
        )}
      </div>
    </button>
  )
}

const FILTERS = [
  { value: 'all', label: 'All', match: () => true },
  { value: 'pending', label: 'Unscraped', match: (m: Media) => m.scrape_status === 'pending' },
  { value: 'partial', label: 'Partial', match: (m: Media) => m.scrape_status === 'partial' },
  { value: 'confirmed', label: 'Scraped', match: (m: Media) => m.scrape_status === 'confirmed' },
  { value: 'incomplete', label: 'Missing data', match: (m: Media) => m.incomplete },
] as const

function MediaGrid({ list, entry, selectedId, onSelect }: {
  list: Media[]
  entry: Entry
  selectedId: number | null
  onSelect: (media: Media, entry: Entry) => void
}) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(8.5rem,1fr))] gap-3 md:grid-cols-[repeat(auto-fill,minmax(9.5rem,1fr))]">
      {sortMedia(list).map(m => (
        <MediaCard
          key={m.id}
          media={m}
          selected={selectedId === m.id}
          onClick={() => onSelect(m, entry)}
        />
      ))}
    </div>
  )
}

function Count({ n, active }: { n: number; active: boolean }) {
  return (
    <span className={cn('ml-1.5 tabular-nums', active ? 'text-foreground/70' : 'text-muted-foreground/70')}>
      {n}
    </span>
  )
}

export function MediaList({ entries, mediaMap, selectedId, onSelect }: Props) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())
  // Tab and filter live in the URL so a reload or a bookmark keeps the view.
  const [params, setParams] = useSearchParams()

  const entryParam = Number(params.get('entry'))
  const activeEntry = entries.find(e => e.id === entryParam) ?? null
  const filter = FILTERS.find(f => f.value === params.get('status')) ?? FILTERS[0]

  function setParam(key: 'entry' | 'status', value: string | null) {
    setParams(prev => {
      const next = new URLSearchParams(prev)
      if (value === null) next.delete(key)
      else next.set(key, value)
      return next
    }, { replace: true })
  }

  function toggleCollapse(id: number) {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  if (entries.length === 0) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No entries. Add one in Settings.
      </div>
    )
  }

  const allMedia = entries.flatMap(e => mediaMap.get(e.id) ?? [])
  // Filter counts follow the selected tab; tab counts are always unfiltered.
  const scope = activeEntry ? mediaMap.get(activeEntry.id) ?? [] : allMedia
  const visibleEntries = activeEntry ? [activeEntry] : entries
  const sections = visibleEntries
    .map(entry => {
      const list = mediaMap.get(entry.id) ?? []
      return { entry, list, shown: list.filter(filter.match) }
    })
    // Under a filter, hide folders with nothing to show.
    .filter(s => filter.value === 'all' || s.shown.length > 0)

  const tabs: { id: number | null; name: string; count: number }[] = [
    { id: null, name: 'All', count: allMedia.length },
    ...entries.map(e => ({ id: e.id, name: e.name, count: (mediaMap.get(e.id) ?? []).length })),
  ]

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b px-4 pt-2">
        <nav className="-mb-px flex min-w-0 max-w-full overflow-x-auto [scrollbar-width:none]">
          {tabs.map(tab => {
            const active = (activeEntry?.id ?? null) === tab.id
            return (
              <button
                key={tab.id ?? 'all'}
                onClick={() => setParam('entry', tab.id === null ? null : String(tab.id))}
                className={cn(
                  'shrink-0 whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors',
                  active
                    ? 'border-primary font-medium text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                )}
              >
                {tab.name}
                <Count n={tab.count} active={active} />
              </button>
            )
          })}
        </nav>
        <div className="mb-2 flex shrink-0 overflow-x-auto rounded-md border p-0.5 [scrollbar-width:none]">
          {FILTERS.map(f => {
            const active = filter.value === f.value
            return (
              <button
                key={f.value}
                onClick={() => setParam('status', f.value === 'all' ? null : f.value)}
                className={cn(
                  'shrink-0 whitespace-nowrap rounded px-2.5 py-1 text-xs transition-colors',
                  active ? 'bg-muted font-medium text-foreground' : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {f.label}
                <Count n={scope.filter(f.match).length} active={active} />
              </button>
            )
          })}
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        {sections.length === 0 && (
          <p className="p-4 text-sm text-muted-foreground">No media match this filter.</p>
        )}
        {activeEntry ? (
          sections.map(({ entry, shown }) => (
            <div key={entry.id} className="p-4">
              {shown.length === 0 && (
                <p className="text-xs text-muted-foreground">No media yet.</p>
              )}
              <MediaGrid list={shown} entry={entry} selectedId={selectedId} onSelect={onSelect} />
            </div>
          ))
        ) : (
          sections.map(({ entry, list, shown }) => {
            const pendingCount = list.filter(m => m.scrape_status === 'pending').length
            const partialCount = list.filter(m => m.scrape_status === 'partial').length
            const isCollapsed = collapsed.has(entry.id)
            return (
              <section key={entry.id} className="border-b">
                <button
                  onClick={() => toggleCollapse(entry.id)}
                  className="sticky top-0 z-10 w-full bg-background/95 px-4 py-3 text-left backdrop-blur hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    {isCollapsed ? (
                      <ChevronRight className="size-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="size-4 text-muted-foreground" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">{entry.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {filter.value === 'all'
                          ? `${list.length} items`
                          : `${shown.length} of ${list.length} items`}
                        {filter.value === 'all' && pendingCount > 0 && ` · ${pendingCount} unscraped`}
                        {filter.value === 'all' && partialCount > 0 && ` · ${partialCount} partial`}
                      </p>
                    </div>
                  </div>
                </button>
                {!isCollapsed && (
                  <div className="px-4 pb-5">
                    {shown.length === 0 && (
                      <p className="py-2 text-xs text-muted-foreground">No media yet.</p>
                    )}
                    <MediaGrid list={shown} entry={entry} selectedId={selectedId} onSelect={onSelect} />
                  </div>
                )}
              </section>
            )
          })
        )}
      </ScrollArea>
    </div>
  )
}
