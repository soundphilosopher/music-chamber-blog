# 🎵🎵🎵 Music Chamber 🎵🎵🎵

> _"What happens when you lock a musician, developer, and philosopher in a room with too many albums? This blog."_

**Music Chamber** is a lovingly curated music blog where new releases get listened to, dissected, and sometimes lovingly roasted — all in one place. Every week, dozens of fresh albums across every genre imaginable get a short, honest take. From Norwegian post-black-metal to Brazilian prog, from Texan nu-metal to Scandinavian neo-classical ambient piano — if it dropped this week, it's probably in here.

Built with [MkDocs Material](https://squidfund.github.io/mkdocs-material/) and powered by stubbornness and good taste. 🔥

---

## 🎧 What's Inside?

| Content | Description |
|---|---|
| 📰 **Weekly Release Lists** | Every Friday, a fresh batch of album reviews — dozens of releases, each with a concise, opinionated take (auf Deutsch! 🇩🇪) |
| ⭐ **Top Picks** | Standout releases are marked and automatically transformed into highlighted cards so they pop off the page |
| 📊 **Monthly Top Lists** | The best of each month, complete with album artwork in a beautiful grid layout |
| 🏆 **Yearly Top 25** | The cream of the crop — a ranked year-end list with cover art |
| 💎 **Top 25 Lifetime** | The all-time hall of fame. Beatles to Portishead. Wire to N.W.A. No genre left behind. |
| 📡 **RSS Feed** | Subscribe to the blog via RSS and never miss a release |

---

## 🛠️ How It Works

This isn't just a bunch of Markdown files (okay, it _mostly_ is) — there's some clever automation under the hood:

### The Star System ⭐

Releases that deserve extra attention get stars in their headings:

- **`*`** — A noteworthy release (highlighted with a subtle border)
- **`**`** — A top-tier pick (highlighted with a bold deep-orange border)

A custom [MkDocs hook](scripts/hooks/mark_top_picks.py) powered by BeautifulSoup parses the HTML at build time and wraps starred entries in styled Material card components. No manual HTML fiddling required.

### Auto-Generated Recaps 🤖

A [generator script](scripts/generators/current_recap_list.py) crawls all the weekly release lists, collects every starred entry, and automatically produces monthly recap pages — grouped by month, linked back to the original review. Write your reviews, sprinkle some stars, and the recaps build themselves.

### Image Source Rewriting 🖼️

A [hook](scripts/hooks/image_src_with_site_url.py) rewrites image sources that use the `site:` prefix, replacing them with the absolute site URL at build time. This keeps image paths portable in Markdown while ensuring they resolve correctly in blog excerpts and the full rendered site.

### RSS Feed 📡

The [mkdocs-rss-plugin](https://guts.github.io/mkdocs-rss-plugin/) generates an RSS feed from all posts, so readers can subscribe and get updates whenever new release lists or top picks are published. Post creation dates are pulled from front-matter metadata, and categories are included in the feed.

---

## 🚀 Getting Started

### Prerequisites

- Python **3.14+** (yes, we live on the bleeding edge 🐍)

### Setup

```bash
git clone https://github.com/soundphilosopher/music-chamber-blog.git
cd music-chamber-blog
```

Then run the setup script:

```bash
./scripts/setup_docs.sh
```

This will:
1. Install all dependencies via `pip install -e .`
2. Build the site with `mkdocs build`
3. Fire up a local dev server at **http://127.0.0.1:8000**

### Or do it manually:

```bash
pip install -e .
mkdocs serve -w .
```

> 💡 **Tip:** Draft posts and future-dated posts are only visible when using `mkdocs serve` — they won't appear in production builds.

### Using Anaconda / Miniconda 🐍

If you prefer [Anaconda](https://www.anaconda.com/) or [Miniconda](https://docs.anaconda.com/miniconda/) for environment management:

1. **Create a dedicated conda environment with Python 3.14:**

   ```bash
   conda create -n music-chamber python=3.14 -y
   conda activate music-chamber
   ```

2. **Install the project and all its dependencies:**

   ```bash
   pip install -e .
   ```

   > ℹ️ All dependencies are pure-Python wheels (MkDocs, BeautifulSoup, curl-cffi, etc.) and install cleanly via `pip` inside a conda environment. There is no need for `conda install` for any of them.

3. **Build & serve the site:**

   ```bash
   mkdocs serve -w .
   ```

   The site will be available at **http://127.0.0.1:8000**.

Alternatively, you can run the setup script after activating the environment:

```bash
conda activate music-chamber
./scripts/setup_docs.sh
```

To deactivate or remove the environment later:

```bash
conda deactivate
conda env remove -n music-chamber
```

---

## 🎨 Theming

The blog rocks a **deep orange** primary with **deep purple** accents on Material for MkDocs, because apparently we're designing a 70s prog album cover. Light and dark mode included, naturally. 🌗

Custom CSS handles the special card styling for top picks and tweaks admonition borders to keep things clean.

---

## 📁 Project Structure

```
music-chamber/
├── docs/
│   ├── .authors.yml                    # Blog author metadata
│   ├── index.md                        # Blog landing page
│   ├── assets/
│   │   ├── images/                     # Album artwork for top lists
│   │   ├── append.css                  # Card & chip styles
│   │   └── override.css                # Admonition tweaks
│   └── posts/
│       ├── 2025/
│       │   ├── 04/25/releases.md       # Weekly release lists
│       │   ├── 05/02/releases.md
│       │   ├── ...
│       │   └── 12/                     # top-25-lifetime, etc.
│       └── 2026/
│           ├── 01/
│           │   ├── 09/releases.md
│           │   ├── 16/releases.md
│           │   ├── ...
│           │   ├── top-25-recap-2025.md
│           │   └── top-of-the-month.md
│           ├── 02/
│           │   ├── 06/releases.md
│           │   ├── ...
│           │   └── top-of-the-month.md
│           └── 03/
│               └── top-of-the-month.md
├── scripts/
│   ├── generators/
│   │   └── monthly_recap_draft.py      # Auto-generates monthly recaps
│   │   └── genre_overview.py           # Auto-generates genre overview
│   ├── hooks/
│   │   ├── add_bandcamp_player.py      # Add the Bandcamp player iframe to pinned releases
│   │   ├── add_release_count.py        # Add release count to metadate view on release lists
│   │   ├── cleanup_tags.py             # Removes HTML tags
│   │   ├── filter_genres.py            # Add fuzzy filter input to auto-generated genres page
│   │   ├── image_src_with_site_url.py  # Rewrites site:-prefixed image sources
│   │   └── mark_top_picks.py           # Transforms starred entries into cards
│   ├── setup_docs.sh                   # One-command setup
│   └── import_images.py                # Import images (helper script)
├── mkdocs.yml                          # Site configuration
└── pyproject.toml                      # Python project config
```

---

## 🎶 Genre Coverage

Think we only cover one genre? Think again. Here's a taste of what you'll find in any given week:

`Death Metal` · `Progressive Rock` · `Ambient` · `Jazz` · `Post-Punk` · `Indie Rock` · `Doom/Sludge` · `Electronica` · `Krautrock` · `Shoegaze` · `Neo-Classical` · `Metalcore` · `Synth-Pop` · `Drum & Bass` · `Psychedelic` · `Folk` · `Thrash` · `Trip-Hop` · `Drone` · `Skate Punk` · `Glam Punk` · `Nu-Metal` · `Goth Rock` · `Fusion Jazz` · `Post-Bop` · `Space Rock` · `Stoner Rock` · `Alt-Pop` · `Singer-Songwriter` · `Breakbeat` · `Arena Rock` · _...and whatever else drops on a Friday_

---

## ✍️ Author

**Carsten Vuellings** — musician, developer, systems architect, philosopher, author, and founder.

Built with 🧡 and an unreasonable number of headphones.

---

## 📄 License

This project contains original music commentary and reviews. All album artwork belongs to their respective artists and labels.
