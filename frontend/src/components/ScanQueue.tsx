import { useState } from 'react'
import { toast } from 'sonner'
import { confirmAdd, confirmRemove, type ScanResultItem } from '@/api/scan'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

interface Props {
  results: ScanResultItem[]
  onConfirmedAdd: (entryId: number, sourceName: string) => void
  onConfirmedRemove: (entryId: number, mediaId: number) => void
}

export function ScanQueue({ results, onConfirmedAdd, onConfirmedRemove }: Props) {
  const [loading, setLoading] = useState<string | null>(null)

  const allRows = results.flatMap(r => [
    ...r.added.map(item => ({ type: 'add' as const, entryId: r.entry_id, entryName: r.entry_name, name: item.source_name, videoStem: item.video_stem, id: `add-${r.entry_id}-${item.source_name}` })),
    ...r.removed.map(m => ({ type: 'remove' as const, entryId: r.entry_id, entryName: r.entry_name, name: m.source_name, mediaId: m.id, id: `rm-${m.id}` })),
  ])

  if (allRows.length === 0) return null

  async function handleAdd(entryId: number, sourceName: string, videoStem: string | null) {
    const key = `add-${entryId}-${sourceName}`
    setLoading(key)
    try {
      await confirmAdd(entryId, sourceName, videoStem)
      toast.success(`Added: ${sourceName}`)
      onConfirmedAdd(entryId, sourceName)
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

  return (
    <div className="border-b bg-muted/40">
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
                row.type === 'add' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}
            >
              {row.type === 'add' ? '+' : '−'}
            </span>
            <span className="font-mono flex-1 truncate">{row.name}</span>
            <span className="text-muted-foreground shrink-0">→ {row.entryName}</span>
            <Button
              size="sm"
              variant={row.type === 'add' ? 'default' : 'destructive'}
              className="h-6 px-2 text-xs shrink-0"
              disabled={loading === row.id}
              onClick={() =>
                row.type === 'add'
                  ? handleAdd(row.entryId, row.name, row.videoStem)
                  : handleRemove(row.entryId, row.mediaId!, row.name)
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
