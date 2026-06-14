import { useState } from 'react'
import { toast } from 'sonner'
import { confirmAdd, confirmEpisodeUpdates, confirmRemove, type ScanResultItem } from '@/api/scan'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

interface Props {
  results: ScanResultItem[]
  onConfirmedAdd: (entryId: number, sourceName: string) => void
  onConfirmedRemove: (entryId: number, mediaId: number) => void
  onConfirmedEpisodeUpdates: (entryId: number, mediaId: number) => void
}

export function ScanQueue({ results, onConfirmedAdd, onConfirmedRemove, onConfirmedEpisodeUpdates }: Props) {
  const [loading, setLoading] = useState<string | null>(null)

  const allRows = results.flatMap(r => [
    ...r.added.map(item => ({ type: 'add' as const, entryId: r.entry_id, entryName: r.entry_name, name: item.source_path, id: `add-${r.entry_id}-${item.source_path}` })),
    ...r.removed.map(m => ({ type: 'remove' as const, entryId: r.entry_id, entryName: r.entry_name, name: m.source_name, mediaId: m.id, id: `rm-${m.id}` })),
    ...r.episode_updates.map(u => ({
      type: 'episodes' as const,
      entryId: r.entry_id,
      entryName: r.entry_name,
      name: u.source_name,
      mediaId: u.media_id,
      files: u.files,
      id: `ep-${u.media_id}-${u.files.join('|')}`,
    })),
  ])

  if (allRows.length === 0) return null

  async function handleAdd(entryId: number, sourcePath: string) {
    const key = `add-${entryId}-${sourcePath}`
    setLoading(key)
    try {
      await confirmAdd(entryId, sourcePath)
      toast.success(`Added: ${sourcePath}`)
      onConfirmedAdd(entryId, sourcePath)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(null)
    }
  }

  async function handleRemove(entryId: number, mediaId: number, sourceName: string) {
    const key = `rm-${mediaId}`
    setLoading(key)
    try {
      await confirmRemove(mediaId)
      toast.success(`Removed: ${sourceName}`)
      onConfirmedRemove(entryId, mediaId)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(null)
    }
  }

  async function handleEpisodeUpdates(entryId: number, mediaId: number, sourceName: string, files: string[]) {
    const key = `ep-${mediaId}-${files.join('|')}`
    setLoading(key)
    try {
      const result = await confirmEpisodeUpdates(mediaId, files)
      toast.success(`Linked ${result.linked} episode${result.linked !== 1 ? 's' : ''}: ${sourceName}`)
      onConfirmedEpisodeUpdates(entryId, mediaId)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="m-3 rounded-lg border bg-muted/40 shadow-sm overflow-hidden">
      <div className="px-4 py-2 flex items-center gap-2">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Scan Results
        </span>
        <span className="text-xs text-muted-foreground">({allRows.length} pending)</span>
      </div>
      <Separator />
      <div className="divide-y">
        {allRows.map(row => (
          <div key={row.id} className="flex items-center gap-3 px-4 py-2 text-sm">
            <span
              className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                row.type === 'add'
                  ? 'bg-green-100 text-green-700'
                  : row.type === 'episodes'
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-red-100 text-red-700'
              }`}
            >
              {row.type === 'add' ? '+' : row.type === 'episodes' ? '~' : '−'}
            </span>
            <span className="font-mono flex-1 truncate">
              {row.type === 'episodes' ? `${row.name} · ${row.files.length} new episode${row.files.length !== 1 ? 's' : ''}` : row.name}
            </span>
            <span className="text-muted-foreground shrink-0">→ {row.entryName}</span>
            <Button
              size="sm"
              variant={row.type === 'remove' ? 'destructive' : 'default'}
              className="h-6 px-2 text-xs shrink-0"
              disabled={loading === row.id}
              onClick={() =>
                row.type === 'add'
                  ? handleAdd(row.entryId, row.name)
                  : row.type === 'episodes'
                    ? handleEpisodeUpdates(row.entryId, row.mediaId, row.name, row.files)
                    : handleRemove(row.entryId, row.mediaId, row.name)
              }
            >
              {loading === row.id ? '…' : 'Confirm'}
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}
