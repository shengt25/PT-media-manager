import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { searchScrape, confirmScrape, rescrape, getPoster, type TmdbCandidate } from '@/api/scrape'
import { type Media } from '@/api/media'
import { type Entry } from '@/api/entries'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

const LANGUAGES = [
  { value: 'zh-CN', label: '中文' },
  { value: 'en-US', label: 'English' },
  { value: 'ja-JP', label: '日本語' },
]

const TMDB_W92  = 'https://image.tmdb.org/t/p/w92'
const TMDB_W342 = 'https://image.tmdb.org/t/p/w342'

interface Props {
  open: boolean
  media: Media | null
  entry: Entry | null
  onClose: () => void
  onDone: () => void
  mode?: 'confirm' | 'rescrape'
}

export function ScrapeModal({ open, media, entry, onClose, onDone, mode = 'confirm' }: Props) {
  const [candidates, setCandidates] = useState<TmdbCandidate[]>([])
  const [selected, setSelected] = useState<TmdbCandidate | null>(null)
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('zh-CN')
  const [imageLanguage, setImageLanguage] = useState('zh-CN')
  const [previewPoster, setPreviewPoster] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [fetchingPoster, setFetchingPoster] = useState(false)

  useEffect(() => {
    if (!open || !media) return
    setCandidates([])
    setSelected(null)
    setPreviewPoster(null)
    setConfirming(false)

    const title = media.source_name.replace(/\.[^.]+$/, '').replace(/[._]/g, ' ').trim()
    setQuery(title)
    setSearching(true)
    searchScrape(media.id, title, undefined, language)
      .then(results => {
        setCandidates(results)
        if (results.length === 1) selectCandidate(results[0], imageLanguage)
      })
      .catch(e => toast.error(e.message))
      .finally(() => setSearching(false))
  }, [open, media?.id])

  function selectCandidate(c: TmdbCandidate, imgLang: string) {
    setSelected(c)
    setPreviewPoster(c.poster_path)
    if (imgLang !== language && entry) {
      fetchPoster(c.tmdb_id, entry.media_type, imgLang)
    }
  }

  async function fetchPoster(tmdbId: number, mediaType: string, imgLang: string) {
    setFetchingPoster(true)
    try {
      const res = await getPoster(tmdbId, mediaType, imgLang)
      setPreviewPoster(res.poster_path)
    } catch {
      // keep current poster on error
    } finally {
      setFetchingPoster(false)
    }
  }

  function handleSelectCandidate(c: TmdbCandidate) {
    setSelected(c)
    setPreviewPoster(c.poster_path)
    if (imageLanguage !== language && entry) {
      fetchPoster(c.tmdb_id, entry.media_type, imageLanguage)
    }
  }

  function handleImageLanguageChange(lang: string | null) {
    if (lang == null) return
    setImageLanguage(lang)
    if (selected && entry && lang !== language) {
      fetchPoster(selected.tmdb_id, entry.media_type, lang)
    } else if (selected && lang === language) {
      setPreviewPoster(selected.poster_path)
    }
  }

  async function handleSearch() {
    if (!media) return
    setSearching(true)
    setSelected(null)
    setPreviewPoster(null)
    try {
      const results = await searchScrape(media.id, query, undefined, language)
      setCandidates(results)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setSearching(false)
    }
  }

  async function handleConfirm() {
    if (!media || !selected) return
    setConfirming(true)
    try {
      const imgLang = imageLanguage !== language ? imageLanguage : undefined
      if (mode === 'rescrape') {
        await rescrape(media.id, selected.tmdb_id, language, imgLang)
      } else {
        await confirmScrape(media.id, selected.tmdb_id, language, imgLang)
      }
      toast.success('Scraped successfully')
      onDone()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
      setConfirming(false)
    }
  }

  if (!media || !entry) return null
  const displayName = media.video_stem ?? media.source_name

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogContent className="max-w-4xl sm:max-w-4xl p-0 overflow-hidden" showCloseButton={false}>
        <div className="flex flex-col h-[600px]">
          {/* header */}
          <div className="flex items-center justify-between px-5 py-3 border-b shrink-0">
            <DialogTitle className="font-mono text-sm text-muted-foreground font-normal truncate">
              {displayName}
            </DialogTitle>
          </div>

          {/* search + language bar */}
          <div className="flex gap-2 px-4 py-3 border-b shrink-0">
            <div className="flex items-center gap-2 w-full">
              <Select value={language} onValueChange={v => { if (v != null) setLanguage(v) }}>
                <SelectTrigger className="h-8 w-28 text-sm shrink-0">
                  <SelectValue>{LANGUAGES.find(l => l.value === language)?.label}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {LANGUAGES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
                </SelectContent>
              </Select>
              <Input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search TMDB…"
                className="h-8 text-sm flex-1"
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
              />
              <Button size="sm" variant="outline" onClick={handleSearch} disabled={searching} className="shrink-0">
                {searching ? '…' : 'Search'}
              </Button>
            </div>
          </div>

          {/* body */}
          <div className="flex flex-1 overflow-hidden">
            {/* left: candidates */}
            <div className="w-72 shrink-0 border-r flex flex-col">
              <ScrollArea className="flex-1">
                <div className="p-2 space-y-1">
                  {candidates.length === 0 && !searching && (
                    <p className="text-sm text-muted-foreground text-center py-6">No results.</p>
                  )}
                  {candidates.map(c => (
                    <button
                      key={c.tmdb_id}
                      onClick={() => handleSelectCandidate(c)}
                      className={cn(
                        'flex items-center gap-2 p-2 rounded-md w-full text-left transition-colors',
                        selected?.tmdb_id === c.tmdb_id
                          ? 'bg-primary/10 border border-primary/30'
                          : 'hover:bg-accent'
                      )}
                    >
                      {c.poster_path
                        ? <img src={`${TMDB_W92}${c.poster_path}`} alt="" className="w-8 h-11 object-cover rounded shrink-0" />
                        : <div className="w-8 h-11 bg-muted rounded shrink-0" />
                      }
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{c.title}</p>
                        <p className="text-xs text-muted-foreground">{c.year ?? '-'} · ★ {c.rating?.toFixed(1) ?? '-'}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* right: selected detail */}
            <div className="flex-1 overflow-y-auto p-5">
              {selected ? (
                <div className="flex gap-4">
                  <div className="shrink-0 space-y-2">
                    {previewPoster
                      ? <img src={`${TMDB_W342}${previewPoster}`} alt="" className={cn('w-32 rounded-lg shadow', fetchingPoster && 'opacity-50')} />
                      : <div className="w-32 h-48 bg-muted rounded-lg" />
                    }
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Poster</p>
                      <Select value={imageLanguage} onValueChange={handleImageLanguageChange}>
                        <SelectTrigger className="h-7 w-32 text-xs">
                          <SelectValue>{LANGUAGES.find(l => l.value === imageLanguage)?.label}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          {LANGUAGES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-base leading-tight">{selected.title}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-sm text-muted-foreground">{selected.year ?? '-'}</span>
                      {selected.rating != null && (
                        <Badge variant="secondary">★ {selected.rating.toFixed(1)}</Badge>
                      )}
                    </div>
                    {selected.overview && (
                      <p className="text-sm text-muted-foreground mt-3 leading-relaxed">{selected.overview}</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
                  Select a result from the left.
                </div>
              )}
            </div>
          </div>

          {/* footer */}
          <div className="flex justify-end gap-2 px-5 py-3 border-t shrink-0">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={handleConfirm} disabled={!selected || confirming}>
              {confirming ? 'Confirming…' : 'Confirm'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
