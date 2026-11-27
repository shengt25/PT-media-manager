import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  listEntries, createEntry, updateEntry, deleteEntry,
  type Entry, type EntryCreate,
} from '@/api/entries'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'

const MEDIA_TYPES = [
  { value: 'movie', label: 'Movie' },
  { value: 'tv',   label: 'TV' },
]

const EMPTY_FORM: EntryCreate = { name: '', source_path: '', link_path: '', media_type: 'movie' }

export function Sources() {
  const [entries, setEntries] = useState<Entry[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Entry | null>(null)
  const [form, setForm] = useState<EntryCreate>(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)

  const load = (showLoading = true) => {
    if (showLoading) setLoading(true)
    listEntries()
      .then(setEntries)
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(false) }, [])

  function openAdd() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setDialogOpen(true)
  }

  function openEdit(e: Entry) {
    setEditing(e)
    setForm({ name: e.name, source_path: e.source_path, link_path: e.link_path, media_type: e.media_type })
    setDialogOpen(true)
  }

  async function handleSubmit() {
    setSubmitting(true)
    try {
      if (editing) {
        await updateEntry(editing.id, form)
        toast.success('Entry updated')
      } else {
        await createEntry(form)
        toast.success('Entry created')
      }
      setDialogOpen(false)
      load()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(entry: Entry) {
    if (!confirm(`Delete "${entry.name}" and its link directory?`)) return
    try {
      await deleteEntry(entry.id)
      toast.success('Entry deleted')
      load()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
        <h1 className="text-base font-semibold">Sources</h1>
        <Button size="sm" onClick={openAdd}>Add Entry</Button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Paths</TableHead>
                <TableHead className="w-32" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                    No entries yet. Add one to get started.
                  </TableCell>
                </TableRow>
              )}
              {entries.map(entry => (
                <TableRow key={entry.id}>
                  <TableCell className="font-medium whitespace-nowrap">{entry.name}</TableCell>
                  <TableCell className="capitalize whitespace-nowrap">{entry.media_type}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    <div>
                      <span className="text-foreground/40 select-none">src </span>{entry.source_path}
                    </div>
                    <div className="mt-0.5">
                      <span className="text-foreground/40 select-none">lnk </span>{entry.link_path}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2 justify-end">
                      <Button variant="outline" size="sm" onClick={() => openEdit(entry)}>Edit</Button>
                      <Button variant="destructive" size="sm" onClick={() => handleDelete(entry)}>Delete</Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit Entry' : 'Add Entry'}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <Label>Name</Label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="grid gap-1.5">
              <Label>Source Path</Label>
              <Input value={form.source_path} onChange={e => setForm(f => ({ ...f, source_path: e.target.value }))} />
            </div>
            <div className="grid gap-1.5">
              <Label>Link Path</Label>
              <Input value={form.link_path} onChange={e => setForm(f => ({ ...f, link_path: e.target.value }))} />
            </div>
            <div className="grid gap-1.5">
              <Label>Type</Label>
              <Select value={form.media_type} onValueChange={v => setForm(f => ({ ...f, media_type: v as 'movie' | 'tv' }))}>
                <SelectTrigger>
                  <SelectValue>{MEDIA_TYPES.find(t => t.value === form.media_type)?.label}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {MEDIA_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSubmit} disabled={submitting}>{submitting ? 'Saving…' : 'Save'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
