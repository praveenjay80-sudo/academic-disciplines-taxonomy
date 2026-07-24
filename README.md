# Maths-Physics-CS Knowledge Explorer

Explore Mathematics, Physics, and Computer Science through real, authoritative
classifications — or any other topic on demand — and for any node get its basic
questions (plain language, for beginners), its genuinely open research questions
(with precise literature), and its major theoretical paradigms.

## Structure: real data, not scraped/merged data

Three tabs are backed by real, professionally-maintained classifications, built
once offline (`scripts/build_real_trees.py`) and shipped as static JSON — browsing
them costs nothing and needs no API key:

- **Mathematics** — [MSC2020](https://msc2020.org/) (AMS/zbMATH), ~6,100 topics
- **Physics** — [PhySH](https://physh.org/) (American Physical Society), ~3,900 topics
- **Computer Science** — the full [ACM CCS](https://dl.acm.org/ccs), ~2,300 topics

Non-subject administrative entries (publication-format codes, audience categories
like "K-12 teachers") are filtered out during the build — every remaining node is a
real academic subject.

A fourth **Explore** mode covers everything else: type any topic and its
sub-disciplines are generated live, grounded against the real Wikipedia article text
for that topic (the model filters/organizes what the source actually discusses,
rather than free-recalling from memory).

This replaces an earlier version that scraped and merged 68 Wikipedia "Outline
of..." pages into one static tree — that approach produced a tree with the same
discipline scattered across unrelated branches, because mechanically parsing
heterogeneous pages into structure was the actual problem, not the merge algorithm.
Real classifications (MSC/PhySH/CCS) sidestep that entirely: each is already a
single, coherent, human-curated hierarchy — nothing to merge.

## Per-node features

Click any topic (in a real-data tab, or via Explore) to generate:

- **❓ Basic Questions** — 🌱 Beginner / 🌿 Intermediate / 🌳 Advanced questions the
  field addresses, each with a detailed plain-language explanation assuming zero
  background. Every question gets its own on-demand reading list, from prerequisites
  to current research — shaped specifically to that question, not a shared list for
  the whole topic.
- **🔬 Research Questions** — genuinely open, currently-unsolved problems (not
  educational questions). Each gets its own precise literature list: title, author,
  year, venue, and a DOI/arXiv link when the model is confident of the exact
  value — plus a client-generated Google Books/Scholar search link as a fallback
  that's always valid, since it's a search query rather than a claimed direct URL.
- **🧭 Paradigms** — the field's major competing theoretical frameworks/schools, if
  it genuinely has distinct ones.

Every work shown also explains **what it itself is trying to answer** — its own
central question or claim, separate from why it's relevant to the question you
asked.

Reading lists and literature are grounded against real citations pulled from each
topic's Wikipedia "Further reading"/"Bibliography"/"References" sections when
available, used as the backbone rather than free-recalled from the model's memory.

Everything generated is cached in your browser's IndexedDB, keyed by its full path,
so revisiting a topic is instant and free.

## Usage

1. Open the app (GitHub Pages URL or `index.html` locally)
2. Paste your [OpenRouter API key](https://openrouter.ai/keys) in the settings bar
3. Pick Mathematics / Physics / Computer Science and click any topic in the tree, or
   switch to Explore and type any topic
4. Generate Basic Questions, Research Questions, and/or Paradigms as needed — each
   is its own on-demand call, cached after first generation

Your API key is stored in your browser's localStorage only — it never touches any
server other than OpenRouter's API and Wikipedia's public read API (for grounding).

## Model

Defaults to Gemini 2.5 Flash. DeepSeek V4 Flash is also listed (large output window,
useful for the more exhaustive generations). Pick "Custom model ID…" to use any
other OpenRouter model slug.
