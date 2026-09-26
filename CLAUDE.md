# Release review rulebook

This repo is Carsten's blog. He scaffolds each weekly `docs/posts/YYYY/MM/DD/releases.md`
himself — artist/title headings, a literal `tbd` body, a bare `::genre::` line per release.
The review job is filling both in. Reviews are written in German (the blog is for his
German-speaking friends); repo, code and album titles stay English.

Work in **chunks of 20 entries** per pass — commit/report at each chunk boundary rather than
attempting a whole week in one go.

## Week structure

A release week runs **Saturday → Friday**. The page is dated on its Friday.

- `## Friday` — released on the Friday the page is dated.
- `## Earlier the week` — released Saturday through Thursday before it.

Two listings of the same release are always an error, never a deliberate re-run:

- **Same page, both sections** → keep the `Earlier the week` entry, delete the `Friday` one.
  Move the written review over if only one copy has it.
- **Different weekly pages** → look up the real release date, keep the copy whose Sa–Fr week
  actually contains it. Bandcamp's date is the authority over Apple Music, aggregators, or a
  label page. Ask search questions neutrally — don't lead with a suspected answer.

Each section sorts by **artist only**, case-insensitively. Accent/non-Latin ordering is
genuinely inconsistent in the existing data (sometimes codepoint order, sometimes accent-
stripped) — never mass re-sort a file to "fix" it; flag a violation only if it holds under
both conventions, and ask before touching accent-based ordering.

`<!-- more -->` always sits right after the **third entry** of the `Friday` section, after
its `::genre::` line. It moves whenever the top three Friday entries change — recheck and
reposition it after any add/delete/reorder near the top.

## Verification — do this for every entry, every pass

**Look every release up before writing or re-writing it.** One search per entry: band, album
title, year. Bandcamp's own tag list beats a review outlet's paraphrase when both exist.
Inferring genre from the artist/title name alone is wrong most of the time — a name that
reads as one genre is often another entirely.

**Verification isn't one-and-done.** Re-check entries you've already reviewed when you pass
back through a week, not just new ones — the goal is the list getting more correct over
time, not just staying correct once. A single flagged entry has previously led to a full
re-audit that found several wrong facts, so treat "already reviewed" as a starting point,
not a guarantee.

When a source genuinely can't be found (roughly 1 entry in 9), atmosphere-only writing is
the fallback — but say so explicitly and list those entries; the tags there are guesses.

**"Nothing found" needs more than a search-engine summary before it justifies removal.**
General web search summaries miss real Bandcamp releases surprisingly often — a full re-audit
once found 9 entries wrongly removed as "unverifiable" in a single week, all of them real
releases that a direct Bandcamp fetch caught immediately. Before cutting an entry under
deletion criterion 2 below, try the artist's own Bandcamp handle directly
(`artistname.bandcamp.com/music`, then the specific album page) rather than trusting a search
summary alone. For metal-genre-sounding names, also check Metal Archives
(`site:metal-archives.com` in search — direct fetches of that domain get blocked).

## What belongs on the list

Only **EPs and LPs**. Singles don't belong here.

- Remove an entry only when you're **certain** it's a single — confirm via Bandcamp/label
  format info, don't guess from track count alone (a 2-track release can still be an EP).
- When genuinely unsure, leave it and flag it rather than removing it.

Combined with the existing deletion rules, an entry gets removed (no need to ask) when any
of these hold:
1. Verified date falls outside the page's Sa–Fr window.
2. Nothing can be found about it at all.
3. No source states a genre for it.
4. It's clearly a single, not an EP/LP.

Deleting inside the first three Friday entries moves the excerpt marker — recheck it.
Deleting the only entry using a genre token also removes that token from `genres/index.html`
— expected, verify with a build rather than assuming.

**Exception:** bare `::genre::` placeholders on an *unreviewed* page are Carsten's own
scaffolding, not reviewed entries — never sweep those up under these rules.

## Genre tags

`::genre::` takes lowercase, comma-separated shorthand (`osdm`, `atmo black metal`, `prog`,
`melo`, `d&b`); `scripts/utils/genres.py` expands and capitalises it.

- Reuse a token already used in earlier weeks over inventing a new one.
- No bare umbrella terms — `jazz`, `pop`, `folk`, `rock`, `metal`, `experimental`,
  `singer-songwriter`, `acoustic`, `dance`, `fusion`, `hardcore`, `crossover` don't exist as
  standalone tags; use the specific member (`chamber jazz`, `hardcore punk`, `jazz fusion`).
  `ambient`, `blues`, `noise`, `soul`, `funk`, `drone`, `house`, `techno`, `instrumental`,
  `improvisation` are real tags and stay as-is.
- Before merging a rare tag into a bigger one, check the German prose directly above it —
  if the prose names the specific genre, the tag stays. Rare is not removable on its own;
  a handful of real canonical genres (`ska`, `flamenco`, `ethio jazz`, `rock in opposition`,
  `rabm`) are permanently rare.
- Every `*tronica` genre stands on its own — never fold into a neighbour.
- `instrumental` means **no voice anywhere on the album**: main vocals, guest vocals and spoken
  word (its own genre, `spoken words`) all rule it out. Interludes and purely synthesised or
  sampled voices don't count as vocals. Add it only when a source confirms it (track credits,
  Bandcamp tags, a review) — never infer it from a genre or an artist's other records.
  Append it last, and name it in bold in the prose like any other genre.
  **Exception:** if the release is purely `electronica` or an `*electronica` sub-genre, leave it
  off — that family is instrumental by default, so the tag adds nothing.
- `improvisation` only when a source describes the music itself as improvised (free
  improvisation, improvised live set, recorded in real time). "Improvisational moments" in a
  composed record, or a studio-constructed piece, don't qualify. Same placement as above.
- Batch-check new tokens through `normalize_genre_names` (`scripts/utils/genres.py`) before
  finishing a pass — plain `.capitalize()` mangles acronyms and hyphenated names.

Trailing `*`/`**` on a heading marks a top pick for the monthly recap — preserve exactly.

## Style

Genre names in **bold** inside prose, referenced artists in *italics*. Match the voice of
neighbouring weeks rather than inventing one.

## Working alongside Carsten

He keeps the current `releases.md` open and trims entries live while a session runs — a
shrinking entry count mid-task is him curating, not data loss or a script bug. Don't
enumerate his deletions back to him, don't ask if one was intentional, don't restore
anything he removed. Re-read the file before each new chunk rather than trusting an earlier
count.

## Build & commit

Verify with `uv run properdocs` (bandcamp:false first) before committing anything that
touches genre tokens or file structure.

Commit and push straight to `main` — no feature branches, this is a single-author repo.
Only commit when asked. Short, lowercase commit subjects, detail in the body.
