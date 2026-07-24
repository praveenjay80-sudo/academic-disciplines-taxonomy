# Academic Disciplines — Taxonomy Explorer

Interactive browser for 27,637 academic disciplines scraped from 68 Wikipedia Outline pages.

## Features

- **Taxonomy Browser** — Collapsible tree of 27,637 disciplines across 5 domains (Humanities, Social science, Natural science, Formal science, Applied science), 14 levels deep
- **📖 Reading List Generator** — Select any discipline and generate an exhaustive structured reading list (Foundational → Introductory → Intermediate → Advanced → Research Frontier → Cross-Disciplinary → Reference → Journals → Online Resources) using OpenRouter
- **🔄 Wiki Update Scanner** — Scans all 68 Wikipedia Outline pages for new disciplines added since the last snapshot

## Usage

1. Open the app (GitHub Pages URL or `index.html` locally)
2. Paste your [OpenRouter API key](https://openrouter.ai/keys) in the settings bar
3. Browse or search the taxonomy tree
4. Click any discipline → click "Generate Reading List"

Your API key is stored in your browser's localStorage only — it never touches any server.

## Data

- Source: 68 Wikipedia "Outline of..." pages
- Deduplication: Global name-based dedup across all pages
- Cleaning: Removed people, organizations, awards, and publications; split definition-list "Term – description" entries down to just the term; dropped unsplittable junk (leaked template CSS, empty entries)
- Total: 27,637 terms, max depth 14 levels
