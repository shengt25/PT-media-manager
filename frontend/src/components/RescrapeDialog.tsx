import { useState } from 'react'
import { toast } from 'sonner'
import { syncEpisodes, type ScrapeProgress } from '@/api/scrape'
import { type Media } from '@/api/media'
import { type Entry } from '@/api/entries'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

interface Props {
  open: boolean
  media: Media | null
  entry: Entry | null
  onClose: () => void
  onFullRescrape: () => void   // opens ScrapeModal
  onSynced: () => void         // after sync-episodes completes
}

export function RescrapeDialog({ open, media, entry, onClose, onFullRescrape, onSynced }: Props) {
  const [syncing, setSyncing] = useState(false)
  const [progress, setProgress] = useState<ScrapeProgress | null>(null)

  async function handleSync() {
    if (!media) return
    setSyncing(true)
    setProgress(null)
    try {
      await syncEpisodes(media.id)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
      setSyncing(false)
      return
    }

    const es = new EventSource(`${API_BASE}/scrape/${media.id}/progress`, { withCredentials: true })
    es.onmessage = ev => {
      const state: ScrapeProgress = JSON.parse(ev.data)
      setProgress(state)
      if (!state.done) return
      es.close()
      if (state.error) {
        toast.error(state.error)
      } else {
        toast.success('Sync complete')
        for (const warning of state.warnings) {
          toast.warning(warning)
        }
        onSynced()
      }
      setSyncing(false)
    }
    es.onerror = () => {
      es.close()
      toast.error('Lost connection to scrape progress')
      setSyncing(false)
    }
  }

  if (!media || !entry) return null
  const isTV = entry.media_type === 'tv'
  const canSync = isTV && media.scrape_status === 'partial'

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Re-scrape</DialogTitle>
        </DialogHeader>
        <div className="text-sm text-muted-foreground py-2">
          {isTV
            ? canSync
              ? 'Choose how to update this TV show.'
              : 'This will delete all generated files and re-scrape.'
            : 'This will delete all generated files and re-scrape.'}
        </div>
        <DialogFooter className="flex-col gap-2 sm:flex-col">
          {canSync && syncing && (
            <div className="space-y-1">
              <Progress value={progress?.total ? (progress.current / progress.total) * 100 : null} />
              <p className="text-xs text-muted-foreground">
                {progress?.total ? `Scraping… ${progress.current}/${progress.total}` : 'Starting…'}
              </p>
            </div>
          )}
          {canSync && (
            <Button
              variant="outline"
              className="w-full justify-start"
              disabled={syncing}
              onClick={handleSync}
            >
              {syncing ? 'Scraping…' : 'Incremental scrape'}
              <span className="ml-auto text-xs text-muted-foreground">incremental</span>
            </Button>
          )}
          <Button
            variant="destructive"
            className="w-full justify-start"
            onClick={() => { onClose(); onFullRescrape() }}
          >
            Full re-scrape
            <span className="ml-auto text-xs opacity-70">deletes all, pick new match</span>
          </Button>
          <Button variant="ghost" className="w-full" onClick={onClose}>Cancel</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
