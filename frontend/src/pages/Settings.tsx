import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { getSettings, updateSettings } from '@/api/settings'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function Settings() {
  const [tmdbProxy, setTmdbProxy] = useState('')
  const [savingProxy, setSavingProxy] = useState(false)

  useEffect(() => {
    getSettings()
      .then(s => setTmdbProxy(s.tmdb_proxy ?? ''))
      .catch(e => toast.error(e.message))
  }, [])

  async function handleSaveProxy() {
    setSavingProxy(true)
    try {
      await updateSettings(tmdbProxy.trim() || null)
      toast.success('Proxy saved')
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setSavingProxy(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
        <h1 className="text-base font-semibold">Settings</h1>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-md">
          <h2 className="text-sm font-semibold mb-1">TMDB Proxy</h2>
          <p className="text-xs text-muted-foreground mb-2">
            HTTP/HTTPS proxy used for TMDB API and image requests during scraping. Leave empty to disable.
          </p>
          <div className="flex gap-2">
            <Label className="sr-only" htmlFor="tmdb-proxy">TMDB Proxy</Label>
            <Input
              id="tmdb-proxy"
              placeholder="http://127.0.0.1:7890"
              value={tmdbProxy}
              onChange={e => setTmdbProxy(e.target.value)}
            />
            <Button onClick={handleSaveProxy} disabled={savingProxy}>
              {savingProxy ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
