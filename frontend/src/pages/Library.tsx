import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { listEntries, type Entry } from '@/api/entries'
import { listMedia, type Media } from '@/api/media'
import { runScan, type ScanResultItem } from '@/api/scan'
import { Button } from '@/components/ui/button'
import { ScanQueue } from '@/components/ScanQueue'
import { MediaList } from '@/components/MediaList'
import { DetailPanel } from '@/components/DetailPanel'

export function Library() {
  const [entries, setEntries] = useState<Entry[]>([])
  const [mediaMap, setMediaMap] = useState<Map<number, Media[]>>(new Map())
  const [selectedMedia, setSelectedMedia] = useState<Media | null>(null)
  const [selectedEntry, setSelectedEntry] = useState<Entry | null>(null)
  const [scanResults, setScanResults] = useState<ScanResultItem[]>([])
  const [scanning, setScanning] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadAll = useCallback(async () => {
    try {
      const es = await listEntries()
      setEntries(es)
      const pairs = await Promise.all(es.map(e => listMedia(e.id).then(m => [e.id, m] as const)))
      setMediaMap(new Map(pairs))
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshMedia = useCallback(async (entryId: number) => {
    try {
      const media = await listMedia(entryId)
      setMediaMap(prev => new Map(prev).set(entryId, media))
      if (selectedMedia?.entry_id === entryId) {
        const updated = media.find(m => m.id === selectedMedia.id)
        if (updated) setSelectedMedia(updated)
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    }
  }, [selectedMedia])

  useEffect(() => { loadAll() }, [loadAll])

  async function handleScan() {
    setScanning(true)
    try {
      const results = await runScan()
      const autoRemovedEntries: number[] = []
      for (const r of results) {
        for (const name of r.auto_removed) {
          toast.warning(`[${r.entry_name}] "${name}" was missing from library, DB record removed`)
          autoRemovedEntries.push(r.entry_id)
        }
        for (const note of r.notes) {
          toast.warning(`[${r.entry_name}] ${note}`)
        }
      }
      if (autoRemovedEntries.length > 0) {
        await Promise.all([...new Set(autoRemovedEntries)].map(id => refreshMedia(id)))
      }
      const withDiff = results.filter(r => r.added.length > 0 || r.removed.length > 0 || r.episode_updates.length > 0)
      setScanResults(withDiff)
      if (withDiff.length === 0 && results.every(r => r.auto_removed.length === 0)) {
        toast('No changes detected')
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setScanning(false)
    }
  }

  function handleConfirmedAdd(entryId: number, sourcePath: string) {
    setScanResults(prev =>
      prev.map(r => r.entry_id === entryId ? { ...r, added: r.added.filter(n => n.source_path !== sourcePath) } : r)
          .filter(r => r.added.length > 0 || r.removed.length > 0 || r.episode_updates.length > 0)
    )
    refreshMedia(entryId)
  }

  function handleConfirmedRemove(entryId: number, mediaId: number) {
    setScanResults(prev =>
      prev.map(r => r.entry_id === entryId ? { ...r, removed: r.removed.filter(m => m.id !== mediaId) } : r)
          .filter(r => r.added.length > 0 || r.removed.length > 0 || r.episode_updates.length > 0)
    )
    refreshMedia(entryId)
  }

  function handleConfirmedEpisodeUpdates(entryId: number, mediaId: number) {
    setScanResults(prev =>
      prev.map(r => r.entry_id === entryId ? { ...r, episode_updates: r.episode_updates.filter(u => u.media_id !== mediaId) } : r)
          .filter(r => r.added.length > 0 || r.removed.length > 0 || r.episode_updates.length > 0)
    )
    refreshMedia(entryId)
  }

  function handleSelect(media: Media, entry: Entry) {
    setSelectedMedia(media)
    setSelectedEntry(entry)
  }

  function handleRefresh() {
    if (selectedMedia) refreshMedia(selectedMedia.entry_id)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
        <h1 className="text-base font-semibold">Library</h1>
        <Button size="sm" onClick={handleScan} disabled={scanning}>
          {scanning ? 'Scanning…' : 'Scan'}
        </Button>
      </div>

      {scanResults.length > 0 && (
        <ScanQueue
          results={scanResults}
          onConfirmedAdd={handleConfirmedAdd}
          onConfirmedRemove={handleConfirmedRemove}
          onConfirmedEpisodeUpdates={handleConfirmedEpisodeUpdates}
        />
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden max-lg:flex-col">
        <div className="flex-1 min-w-0 overflow-hidden flex flex-col">
          {loading ? (
            <p className="p-4 text-sm text-muted-foreground">Loading…</p>
          ) : (
            <MediaList
              entries={entries}
              mediaMap={mediaMap}
              selectedId={selectedMedia?.id ?? null}
              onSelect={handleSelect}
            />
          )}
        </div>

        <DetailPanel
          media={selectedMedia}
          entry={selectedEntry}
          onRefresh={handleRefresh}
        />
      </div>
    </div>
  )
}
