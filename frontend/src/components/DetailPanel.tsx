import { useEffect, useState } from 'react'
import { type Media, type Episode, listEpisodes } from '@/api/media'
import { type Entry } from '@/api/entries'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrapeModal } from './ScrapeModal'
import { RescrapeDialog } from './RescrapeDialog'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

interface Props {
  media: Media | null
  entry: Entry | null
  onRefresh: () => void
}

function EpisodeList({ mediaId }: { mediaId: number }) {
  const [entries, setEntries] = useState<Episode[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    listEpisodes(mediaId)
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }, [mediaId])

  if (loading) return <p className="text-xs text-muted-foreground py-2">Loading episodes…</p>
  if (entries.length === 0) return (
    <p className="text-xs text-muted-foreground py-2">
      No episode data. Click Re-scrape → Full re-scrape to generate.
    </p>
  )

  const identified = entries.filter(e => e.season != null)
  const unidentified = entries.filter(e => e.season == null)
  const seasons = [...new Set(identified.map(e => e.season as number))].sort((a, b) => a - b)

  return (
    <div className="mt-4 pt-4 border-t space-y-3">
      {seasons.map(s => (
        <div key={s}>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
            Season {s}
          </p>
          <div className="space-y-0.5">
            {identified
              .filter(e => e.season === s)
              .sort((a, b) => (a.episode ?? 0) - (b.episode ?? 0))
              .map(e => (
                <div key={`${e.season}-${e.episode}`} className="flex items-baseline gap-2 py-0.5 text-sm">
                  <span className="text-muted-foreground w-8 shrink-0 font-mono text-xs">
                    E{String(e.episode).padStart(2, '0')}
                  </span>
                  {e.status === 'no_tmdb_data' ? (
                    <span className="flex-1 text-xs text-amber-700 dark:text-amber-300">No TMDB data</span>
                  ) : (
                    <span className="flex-1 truncate">{e.title ?? '-'}</span>
                  )}
                  {e.aired && (
                    <span className="text-xs text-muted-foreground shrink-0">{e.aired}</span>
                  )}
                </div>
              ))}
          </div>
          <Separator className="mt-2" />
        </div>
      ))}
      {unidentified.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wider mb-1">
            Unidentified files
          </p>
          <div className="space-y-0.5">
            {unidentified.map(e => (
              <div key={e.file} className="py-0.5 truncate font-mono text-xs text-muted-foreground">
                {e.file}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function DetailPanel({ media, entry, onRefresh }: Props) {
  const [scrapeOpen, setScrapeOpen] = useState(false)
  const [scrapeMode, setScrapeMode] = useState<'confirm' | 'rescrape'>('confirm')
  const [rescrapeOpen, setRescrapeOpen] = useState(false)
  const [episodeKey, setEpisodeKey] = useState(0)
  const [posterErrorMediaId, setPosterErrorMediaId] = useState<number | null>(null)

  if (!media || !entry) {
    return (
      <aside className="w-96 shrink-0 border-l p-5 text-muted-foreground text-sm max-lg:h-56 max-lg:w-full max-lg:border-l-0 max-lg:border-t">
        Select a media item from the list.
      </aside>
    )
  }

  const metadata = (media as Media & { metadata?: Record<string, string> }).metadata
  const displayName = media.source_name
  const isTV = entry.media_type === 'tv'
  const isConfirmed = media.scrape_status === 'confirmed'
  const isPartial = media.scrape_status === 'partial'
  const isScraped = isConfirmed || isPartial
  const posterError = posterErrorMediaId === media.id

  function handleRescrapeClick() {
    if (isTV && isScraped) {
      setRescrapeOpen(true)
    } else {
      setScrapeOpen(true)
    }
  }

  return (
    <aside className="w-96 shrink-0 overflow-y-auto border-l p-5 max-lg:h-72 max-lg:w-full max-lg:border-l-0 max-lg:border-t">
      {isScraped && metadata ? (
        <div className="space-y-4">
          <div className="flex gap-3">
            {!posterError ? (
              <img
                src={`${API_BASE}/media/${media.id}/thumb`}
                alt=""
                className="w-24 rounded-md object-cover shadow-sm"
                onError={() => setPosterErrorMediaId(media.id)}
              />
            ) : (
              <div className="h-36 w-24 shrink-0 rounded-md bg-muted" />
            )}
            <div className="min-w-0 flex-1">
              <h2 className="text-base font-semibold leading-tight">
                {metadata.title}
                {metadata.year && <span className="text-muted-foreground font-normal ml-2">({metadata.year})</span>}
              </h2>
              {metadata.originaltitle && metadata.originaltitle !== metadata.title && (
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{metadata.originaltitle}</p>
              )}
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                {metadata.rating && (
                  <Badge variant="secondary">★ {parseFloat(metadata.rating).toFixed(1)}</Badge>
                )}
                <Badge variant="outline" className="capitalize">{entry.media_type}</Badge>
                {isPartial && <Badge variant="outline">Partial</Badge>}
              </div>
            </div>
          </div>
          {metadata.plot && (
            <p className="line-clamp-6 text-sm leading-relaxed text-muted-foreground">{metadata.plot}</p>
          )}
          <div className="mt-4 pt-4 border-t space-y-1">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Details</p>
            <p className="break-words text-xs font-mono text-foreground">{displayName}</p>
            {media.size != null && (
              <p className="text-xs text-muted-foreground">
                {media.size >= 1e9
                  ? `${(media.size / 1e9).toFixed(1)} GB`
                  : `${(media.size / 1e6).toFixed(1)} MB`}
              </p>
            )}
            <p className="text-xs text-muted-foreground">Added {media.date_added.slice(0, 10)}</p>
          </div>
          <div className="flex gap-2 mt-3">
            <Button size="sm" variant="outline" onClick={handleRescrapeClick}>
              {isPartial ? 'Scrape updates' : 'Re-scrape'}
            </Button>
          </div>

          {isTV && <EpisodeList key={episodeKey} mediaId={media.id} />}
        </div>
      ) : (
        <div>
          <p className="text-sm text-muted-foreground mb-3">{entry.name} · {entry.media_type}</p>
          <div className="space-y-1">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Details</p>
            <p className="break-words text-xs font-mono text-foreground">{displayName}</p>
            {media.size != null && (
              <p className="text-xs text-muted-foreground">
                {media.size >= 1e9
                  ? `${(media.size / 1e9).toFixed(1)} GB`
                  : `${(media.size / 1e6).toFixed(1)} MB`}
              </p>
            )}
            <p className="text-xs text-muted-foreground">Added {media.date_added.slice(0, 10)}</p>
          </div>
          <div className="flex gap-2 mt-6">
            <Button onClick={() => { setScrapeMode('confirm'); setScrapeOpen(true) }}>Scrape</Button>
          </div>
        </div>
      )}

      <ScrapeModal
        open={scrapeOpen}
        media={media}
        entry={entry}
        mode={scrapeMode}
        onClose={() => setScrapeOpen(false)}
        onDone={() => { setScrapeOpen(false); setScrapeMode('confirm'); setEpisodeKey(k => k + 1); onRefresh() }}
      />

      <RescrapeDialog
        open={rescrapeOpen}
        media={media}
        entry={entry}
        onClose={() => setRescrapeOpen(false)}
        onFullRescrape={() => { setRescrapeOpen(false); setScrapeMode('rescrape'); setScrapeOpen(true) }}
        onSynced={() => { setRescrapeOpen(false); setEpisodeKey(k => k + 1); onRefresh() }}
      />
    </aside>
  )
}
