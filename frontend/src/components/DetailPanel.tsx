import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { type Media, type Episode, listEpisodes } from '@/api/media'
import { type Entry } from '@/api/entries'
import { skipScrape } from '@/api/scrape'
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
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    listEpisodes(mediaId)
      .then(setEpisodes)
      .catch(() => setEpisodes([]))
      .finally(() => setLoading(false))
  }, [mediaId])

  if (loading) return <p className="text-xs text-muted-foreground py-2">Loading episodes…</p>
  if (episodes.length === 0) return (
    <p className="text-xs text-muted-foreground py-2">
      No episode data. Click Re-scrape → Full re-scrape to generate.
    </p>
  )

  const seasons = [...new Set(episodes.map(e => e.season))].sort((a, b) => a - b)

  return (
    <div className="mt-4 pt-4 border-t space-y-3">
      {seasons.map(s => (
        <div key={s}>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
            Season {s}
          </p>
          <div className="space-y-0.5">
            {episodes.filter(e => e.season === s).map(e => (
              <div key={`${e.season}-${e.episode}`} className="flex items-baseline gap-2 py-0.5 text-sm">
                <span className="text-muted-foreground w-8 shrink-0 font-mono text-xs">
                  E{String(e.episode).padStart(2, '0')}
                </span>
                <span className="flex-1 truncate">{e.title ?? '-'}</span>
                {e.aired && (
                  <span className="text-xs text-muted-foreground shrink-0">{e.aired}</span>
                )}
              </div>
            ))}
          </div>
          <Separator className="mt-2" />
        </div>
      ))}
    </div>
  )
}

export function DetailPanel({ media, entry, onRefresh }: Props) {
  const [scrapeOpen, setScrapeOpen] = useState(false)
  const [scrapeMode, setScrapeMode] = useState<'confirm' | 'rescrape'>('confirm')
  const [rescrapeOpen, setRescrapeOpen] = useState(false)
  const [episodeKey, setEpisodeKey] = useState(0)
  const [posterError, setPosterError] = useState(false)

  useEffect(() => {
    setPosterError(false)
  }, [media?.id])

  if (!media || !entry) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Select a media item from the list.
      </div>
    )
  }

  const metadata = (media as Media & { metadata?: Record<string, string> }).metadata
  const displayName = media.video_stem ?? media.source_name
  const isTV = entry.media_type === 'tv'
  const isConfirmed = media.scrape_status === 'confirmed'

  async function handleSkip() {
    try {
      await skipScrape(media!.id)
      toast('Skipped')
      onRefresh()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    }
  }

  function handleRescrapeClick() {
    if (isTV && isConfirmed) {
      setRescrapeOpen(true)
    } else {
      setScrapeOpen(true)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      {isConfirmed && metadata ? (
        <div className="flex gap-6">
          <div className="shrink-0">
            {!posterError ? (
              <img
                src={`${API_BASE}/media/${media.id}/poster`}
                alt=""
                className="w-36 rounded-lg shadow-md"
                onError={() => setPosterError(true)}
              />
            ) : (
              <div className="w-36 h-52 bg-muted rounded-lg" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-xl font-semibold leading-tight">
              {metadata.title}
              {metadata.year && <span className="text-muted-foreground font-normal ml-2">({metadata.year})</span>}
            </h2>
            {metadata.originaltitle && metadata.originaltitle !== metadata.title && (
              <p className="text-sm text-muted-foreground mt-0.5">{metadata.originaltitle}</p>
            )}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {metadata.rating && (
                <Badge variant="secondary">★ {parseFloat(metadata.rating).toFixed(1)}</Badge>
              )}
              <Badge variant="outline" className="capitalize">{entry.media_type}</Badge>
            </div>
            {metadata.plot && (
              <p className="text-sm text-muted-foreground mt-3 leading-relaxed">{metadata.plot}</p>
            )}
            <div className="mt-4 pt-4 border-t space-y-1">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Details</p>
              <p className="text-xs font-mono text-foreground">{displayName}</p>
              {media.size != null && (
                <p className="text-xs text-muted-foreground">
                  {media.size >= 1e9
                    ? `${(media.size / 1e9).toFixed(1)} GB`
                    : `${(media.size / 1e6).toFixed(1)} MB`}
                </p>
              )}
              <p className="text-xs text-muted-foreground">Added {media.date_added.slice(0, 10)}</p>
            </div>
            <Button size="sm" variant="outline" className="mt-3" onClick={handleRescrapeClick}>
              Re-scrape
            </Button>

            {isTV && <EpisodeList key={episodeKey} mediaId={media.id} />}
          </div>
        </div>
      ) : (
        <div>
          <p className="text-sm text-muted-foreground mb-3">{entry.name} · {entry.media_type}</p>
          <div className="space-y-1">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Details</p>
            <p className="text-xs font-mono text-foreground">{displayName}</p>
            {media.size != null && (
              <p className="text-xs text-muted-foreground">
                {media.size >= 1e9
                  ? `${(media.size / 1e9).toFixed(1)} GB`
                  : `${(media.size / 1e6).toFixed(1)} MB`}
              </p>
            )}
            <p className="text-xs text-muted-foreground">Added {media.date_added.slice(0, 10)}</p>
          </div>
          {media.scrape_status === 'skipped' && (
            <Badge variant="outline" className="mt-3">Skipped</Badge>
          )}
          <div className="flex gap-2 mt-6">
            <Button onClick={() => { setScrapeMode('confirm'); setScrapeOpen(true) }}>Scrape</Button>
            {media.scrape_status !== 'skipped' && (
              <Button variant="outline" onClick={handleSkip}>Skip</Button>
            )}
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
    </div>
  )
}
