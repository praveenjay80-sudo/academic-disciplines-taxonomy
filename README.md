# Academic Disciplines — Explorer

Explore any academic topic: sub-disciplines, a leveled reading list, and the field's
major theoretical paradigms — generated on demand, grounded against a real source,
and cached locally so you never pay to regenerate the same topic twice.

## How it works

There is no pre-built taxonomy file. Every node is generated the first time you
visit it:

1. A short, real grounding extract is fetched for the topic (Wikipedia's plain-text
   article intro — never parsed as structure, just given to the model as context).
2. The model (via OpenRouter, your own key) returns one structured JSON object:
   a short description, 6-14 clean sub-discipline names, a reading list broken into
   Foundational → Introductory → Intermediate → Advanced → Research Frontier, and
   the field's major competing paradigms/schools of thought (if it genuinely has
   any).
3. The result is cached in your browser's IndexedDB, keyed by its full path, so
   revisiting a topic is instant and free.

This replaces an earlier version of this app that scraped and merged 68 Wikipedia
"Outline of..." pages into a static tree. That approach produced a tree riddled with
the same discipline scattered across unrelated branches and deeply-nested nonsense
placements — the problem wasn't the merge algorithm, it was mechanically parsing
heterogeneous real-world pages into structure at all. This version never does that:
real data is only ever grounding context for the model's own judgment, not something
parsed into the tree directly.

## Usage

1. Open the app (GitHub Pages URL or `index.html` locally)
2. Paste your [OpenRouter API key](https://openrouter.ai/keys) in the settings bar
3. Type any topic, or click one of the five starting domains
4. Click a sub-discipline card to drill in — each generates on first visit, then
   loads instantly from cache
5. Use "↻ Regenerate" on a node to refresh it if the content looks off

Your API key is stored in your browser's localStorage only — it never touches any
server other than OpenRouter's API and Wikipedia's public read API (for grounding).

## Model

Defaults to OpenRouter's `openai/gpt-4o-mini`. Switch models in the settings bar, or
pick "Custom model ID…" to use any OpenRouter model slug directly.
