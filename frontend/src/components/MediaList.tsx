import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
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

export function MediaList({ entries, mediaMap, selectedId, onSelect }: Props) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())

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

  return (
    <ScrollArea className="h-full">
      {entries.map(entry => {
        const list = mediaMap.get(entry.id) ?? []
        const sorted = sortMedia(list)
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
                    {list.length} items
                    {pendingCount > 0 && ` · ${pendingCount} unscraped`}
                    {partialCount > 0 && ` · ${partialCount} partial`}
                  </p>
                </div>
              </div>
            </button>
            {!isCollapsed && (
              <div className="px-4 pb-5">
                {list.length === 0 && (
                  <p className="py-2 text-xs text-muted-foreground">No media yet.</p>
                )}
                <div className="grid grid-cols-[repeat(auto-fill,minmax(8.5rem,1fr))] gap-3 md:grid-cols-[repeat(auto-fill,minmax(9.5rem,1fr))]">
                  {sorted.map(m => (
                    <MediaCard
                      key={m.id}
                      media={m}
                      selected={selectedId === m.id}
                      onClick={() => onSelect(m, entry)}
                    />
                  ))}
                </div>
              </div>
            )}
          </section>
        )
      })}
    </ScrollArea>
  )
}
