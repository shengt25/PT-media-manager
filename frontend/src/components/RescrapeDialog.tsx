import { useState } from 'react'
import { toast } from 'sonner'
import { syncEpisodes } from '@/api/scrape'
import { type Media } from '@/api/media'
import { type Entry } from '@/api/entries'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'

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

  async function handleSync() {
    if (!media) return
    setSyncing(true)
    try {
      const result = await syncEpisodes(media.id)
      toast.success(`Added ${result.added} episode NFO${result.added !== 1 ? 's' : ''}`)
      for (const warning of result.warnings) {
        toast.warning(warning)
      }
      onSynced()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
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
