# New York Kayak Polo — Website

The website for [New York Kayak Polo](https://nykayakpolo.org), a 100% volunteer-run
501(c)(3) nonprofit. Built as a **static site** with [Hugo](https://gohugo.io) and the
[dot-org](https://github.com/cncf/dot-org-hugo-theme) theme, and deployed for free to
**GitHub Pages**. No database, no PHP, nothing to keep patched — just HTML/CSS/JS.

## Toolchain

All tools (Hugo + Node) are managed per-project with [pixi](https://pixi.sh) — nothing is
installed globally. After cloning, run everything through `pixi run …`.

| Command | What it does |
|---|---|
| `pixi run setup` | Install Node build deps (runs automatically before `dev`/`build`) |
| `pixi run dev`   | Start a local preview at <http://localhost:1313> with live reload |
| `pixi run build` | Build the production site into `./public` |
| `pixi run index` | Rebuild the Pagefind search index (CI does this automatically) |

> **Why pixi *and* npm?** pixi manages the *environment* — it pins the exact `hugo` and
> `node` versions in `pixi.lock` (for both macOS and Linux/CI). The theme's build
> *libraries* (PostCSS, autoprefixer, Dart Sass) are npm packages in `package.json`, so
> `pixi run setup` runs `npm install` under the hood. You only ever run `pixi run …`;
> npm is an implementation detail. The GitHub Actions deploy uses the same `pixi.lock`,
> so CI builds with an identical toolchain to your machine.

First time on a new machine:

```bash
git clone --recurse-submodules <repo-url>
cd nykp-website
pixi run dev      # open http://localhost:1313
```

> The theme lives in `themes/dot-org-hugo-theme` as a **git submodule**. If you cloned
> without `--recurse-submodules`, run `git submodule update --init --recursive`.

## Editing content

All page text is in **`content/en/`** as Markdown — edit these, no coding required:

| File | Page |
|---|---|
| `_index.md`     | Home |
| `about.md`      | About (club structure + leadership committee) |
| `game.md`       | The Game (rules) |
| `schedule.md`   | Schedule |
| `membership.md` | Membership |
| `location.md`   | Location |
| `events.md`     | Events and tournaments |
| `links.md`      | Links |
| `contact.md`    | Contact |

- **Navigation menu, footer, social links, and calls-to-action** live in
  `config/_default/languages.yaml` and `config/_default/params.yaml`.
- **Outstanding content tasks** are tracked in [`TODO.md`](TODO.md).
- **Images** live in `static/img/`. The logo and action photos were migrated from the
  old WordPress site; image buttons (Meetup, Donate) are in `static/img/buttons/`.
- **Colors and brand tweaks** are in `static/css/custom.css` (loaded after the theme's
  stylesheet). It swaps the theme's green for the NYKP black/yellow/blue palette and
  styles the `.img-button` image links.
- Pages use the theme's shortcodes (`columns`, `cards`, `button`, `img`, `intro`,
  `spacer`) — see any existing page for examples, or the
  [theme demo](https://dot-org-hugo-theme-demo.netlify.app/demo-page/).

The contact form was intentionally replaced with a **`mailto:` link** to
`info@nykayakpolo.org` — a static site has no server to process form submissions, and a
mailto link needs no third-party service.

## Deployment (GitHub Pages)

Every push to `main` triggers `.github/workflows/hugo.yml`, which builds the site and
publishes it to GitHub Pages automatically. To set it up the first time:

1. Push this repo to GitHub.
2. In the repo: **Settings → Pages → Build and deployment → Source → GitHub Actions**.
3. Push to `main` (or use **Actions → Deploy Hugo site → Run workflow**). The site
   deploys in ~1 minute.
4. Under **Settings → Pages → Custom domain**, enter `nykayakpolo.org` and save.
   (The `static/CNAME` file already pins this domain.) Enable **Enforce HTTPS** once the
   certificate is issued.

### DNS at IONOS

Point the domain at GitHub Pages by editing the DNS records for `nykayakpolo.org` in the
IONOS control panel:

| Type  | Host/Name | Value |
|-------|-----------|-------|
| A     | `@`       | `185.199.108.153` |
| A     | `@`       | `185.199.109.153` |
| A     | `@`       | `185.199.110.153` |
| A     | `@`       | `185.199.111.153` |
| CNAME | `www`     | `<your-github-username>.github.io.` |

Remove any old A/CNAME records that pointed at the previous IONOS WordPress server.
DNS changes can take up to a few hours to propagate. The old IONOS webspace/hosting can
be cancelled once the new site is live (keep the **domain registration** at IONOS).

## What this replaces

The previous site was WordPress on IONOS shared hosting, which broke on a PHP upgrade.
The original content is archived (for reference only) in `wayback-archive-2026-04-10/`,
which is git-ignored and not part of the published site.
