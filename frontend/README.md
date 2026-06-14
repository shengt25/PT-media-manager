# Frontend

React frontend for PT Media Manager.

## Stack

- **React 19** + **TypeScript**
- **Vite**: build tool and dev server
- **shadcn/ui**: component library (base-ui primitives)
- **Tailwind CSS v4**: styling
- **React Router v7**: client-side routing
- **sonner**: toast notifications
- Native `fetch`: no state management library

## Structure

```
src/
  api/
    client.ts       Base fetch wrapper (reads VITE_API_BASE env var)
    entries.ts      Entry CRUD
    media.ts        Media list, episode list
    scan.ts         Scan + confirm-add/remove
    scrape.ts       TMDB search, confirm, rescrape, poster fetch
  pages/
    Library.tsx     Main page: media list + detail panel + scan queue
    Settings.tsx    Entry management (add/edit/delete)
  components/
    Layout.tsx      App shell with sidebar
    Sidebar.tsx     Navigation links
    MediaList.tsx   Left panel: entry groups + media rows
    DetailPanel.tsx Right panel: metadata, episode list, scrape actions
    ScanQueue.tsx   Top bar: pending add/remove items
    ScrapeModal.tsx TMDB search modal (left: candidates, right: detail + poster)
    RescrapeDialog.tsx  TV rescrape options (sync episodes / full rescrape)
```

## Pages

- `/library`: main view. Left: collapsible entry groups with media rows (poster thumbnail, title, scrape status). Right: selected media detail with metadata, artwork, episode list for TV.
- `/settings`: entry CRUD (name, source path, link path, media type).

## API base URL

Controlled by `VITE_API_BASE` environment variable:
- Development: `http://localhost:8000` (default in `client.ts`)
- Production: set `VITE_API_BASE=/api` in `.env.production`, nginx proxies `/api/` to backend

## Running

```bash
npm install
npm run dev      # http://localhost:5173

npm run build    # outputs to dist/
```
