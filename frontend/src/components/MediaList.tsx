import { useState } from 'react'
import { type Entry } from '@/api/entries'
import { type Media } from '@/api/media'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/scroll-area'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

interface Props {
  entries: Entry[]
  mediaMap: Map<number, Media[]>
  selectedId: number | null
  onSelect: (media: Media, entry: Entry) => void
}

function StatusDot({ status }: { status: string }) {
  if (status === 'confirmed') return <span className="w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" />
  if (status === 'pending') return <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
  return <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 shrink-0" />
}

function MediaRow({ media, selected, onClick }: { media: Media; selected: boolean; onClick: () => void }) {
  const [posterError, setPosterError] = useState(false)
  const displayName = media.source_name
  const metadata = (media as Media & { metadata?: Record<string, string> }).metadata

  const title = metadata?.title
  const year = metadata?.year
  const label = title ? `${title}${year ? ` (${year})` : ''}` : displayName

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2.5 px-3 py-1.5 text-left transition-colors',
        selected ? 'bg-accent' : 'hover:bg-accent/50'
      )}
    >
      {!posterError ? (
        <img
          src={`${API_BASE}/media/${media.id}/poster`}
          alt=""
          className="w-7 h-10 object-cover rounded shrink-0"
          onError={() => setPosterError(true)}
        />
      ) : (
        <div className="w-7 h-10 bg-muted rounded shrink-0" />
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm truncate leading-snug">{label}</p>
        {media.scrape_status === 'pending' && (
          <p className="text-xs text-amber-600">Unscraped</p>
        )}
        {media.scrape_status === 'skipped' && (
          <p className="text-xs text-muted-foreground">Skipped</p>
        )}
      </div>
      <StatusDot status={media.scrape_status} />
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
        const isCollapsed = collapsed.has(entry.id)
        return (
          <div key={entry.id}>
            <button
              onClick={() => toggleCollapse(entry.id)}
              className="w-full flex items-center gap-1.5 px-3 py-2 text-left hover:bg-muted/50 transition-colors"
            >
              <span className="text-xs text-muted-foreground">{isCollapsed ? '▶' : '▼'}</span>
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex-1">
                {entry.name}
              </span>
              <span className="text-xs text-muted-foreground">{list.length}</span>
            </button>
            {!isCollapsed && (
              <div>
                {list.length === 0 && (
                  <p className="px-4 py-2 text-xs text-muted-foreground">No media yet.</p>
                )}
                {list.map(m => (
                  <MediaRow
                    key={m.id}
                    media={m}
                    selected={selectedId === m.id}
                    onClick={() => onSelect(m, entry)}
                  />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </ScrollArea>
  )
}
