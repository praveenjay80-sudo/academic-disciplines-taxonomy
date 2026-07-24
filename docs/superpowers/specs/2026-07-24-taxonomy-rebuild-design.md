# Taxonomy Rebuild — Phase 1: Correct, Exhaustive Base Tree

## Status
Approved for implementation. This is Phase 1 of a two-phase rebuild. Phase 2 (reading
list generator rebuild, wiki scanner fix, new "expand node" feature, OpenRouter model
list update) will get its own design doc after Phase 1 ships, since the app rebuild
depends on having a correct base tree to build on.

## Problem

The current `taxonomy.json` (6,806 nodes, scraped from 68 Wikipedia "Outline of..."
pages) has real structural bugs, not just gaps:

- **Duplicate un-merged sibling branches.** Under "Social science", "Anthropology"
  appears as both a 251-item branch and a separate 20-item branch. Same pattern for
  Business/Business studies, Economics, Geography, Linguistics, Political science,
  Psychology, Sociology, Law (and under Applied science: Education, Military
  science(s), Environmental studies, Social work, Architecture).
- **An anomalous "Public administration" branch with 902 items** under Applied
  science — larger than the entirety of Formal science. It doesn't correspond to any
  of the 68 source pages, so it's not traceable to a real source; it's very likely a
  leftover from an earlier, different (lower-quality) scraping pass, not something
  the current pipeline produced.
- **Shallow top-level structure in some domains** — Natural science has only 2 direct
  children (Physical Science, Life science) and Formal science only 3 (Computer
  science, Logic, Mathematics), which is suspicious for domains that should show
  Physics/Chemistry/Astronomy/Earth science, Statistics/Systems science etc. as
  visible branches.

### Root cause (confirmed by reading `build_taxonomy.py`)

`merge_trees(tree_a, tree_b)` only merges `tree_b`'s **top-level** nodes against
`tree_a`'s **top-level** nodes, matching by normalized name. The base skeleton
(`Outline_of_academic_disciplines`) has 5 top-level nodes (the 5 domains). Every other
outline page's top-level headings have completely different names than those 5
domains (e.g. `Outline_of_anthropology`'s top H2 sections are things like "Branches of
anthropology", not "Social science"). Since these don't match anything in the
top-level `nodes_by_name` dict, that page's content gets appended as new top-level
siblings — or, when it does have to nest, it lands in whatever the flat merge order
happens to produce, rather than under the discipline's true existing home in the
skeleton. Result: the same discipline can end up represented in two different places.

## Goal

A taxonomy tree built solely from the 68 Wikipedia "Outline of..." pages, where:

- Every discipline is correctly nested in exactly one place — no duplicate sibling
  branches anywhere in the tree.
- No orphaned/anomalous branches that don't trace back to one of the 68 source pages.
- The 5-domain skeleton is preserved as the top level, matching the current app and
  README ("6,806-ish disciplines across 5 domains").

## Non-goals (explicitly out of scope for Phase 1)

- Merging in OpenAlex concepts, ANZSRC FOR codes, CIP codes, or MeSH — the partially-
  fetched enrichment data in `taxonomy_raw/` (`openalex_concepts.json`,
  `anzsrc_for.json`, `mesh_tree.json`) is not used. The taxonomy stays
  Wikipedia-outline-only, matching the current README's stated scope.
- Crawling beyond the 68 outline pages into linked discipline articles.
- Any app/UI changes (`index.html`) — that's Phase 2.
- Cleaning up the loose `academic-disciplines-*` / `taxonomy_raw/` files sitting in
  the home directory outside this repo clone. Those look like leftovers from earlier,
  unrelated experiments and are left untouched.

## Approach

Work happens in a fresh clone of the repo (`~/Projects/academic-disciplines-taxonomy`),
not the loose home-directory files. The already-cached raw Wikipedia HTML in
`~/taxonomy_raw/wiki_Outline_of_*.html` (68 files) is reused as input — no re-fetching
needed unless a page is missing or parsing reveals it needs a re-fetch.

1. **Reuse the existing HTML→tree parser** (`parse_wiki_html_to_tree` in
   `build_taxonomy.py`) — it looks structurally sound (handles headings, nested lists,
   skips References/See also/etc. sections). Parse each of the 68 pages independently
   from cached HTML.

2. **Rewrite the merge step.** Instead of a flat top-level merge:
   - Keep `Outline_of_academic_disciplines` as the 5-domain skeleton.
   - Build a page → anchor-node mapping: for each of the other 67 pages, derive the
     discipline name from its title (e.g. `Outline_of_anthropology` → "Anthropology")
     and search the *entire* skeleton tree (not just top level) for an existing node
     with that normalized name.
   - If found, merge that page's parsed tree into the matched node's children
     (recursive name-based merge, same `merge_nodes` logic as today, just invoked at
     the right depth instead of always at the root).
   - If not found anywhere in the skeleton, resolve its correct parent via a small
     manual mapping table (most of the 68 pages are sub-branches of one of the 5
     domains or of a mid-level node already in the skeleton — e.g.
     `Outline_of_energy_storage` → under Applied science → Engineering and
     technology → Energy technology). Build this table by inspecting each
     unmatched page once during implementation.

3. **Global post-merge dedup pass.** After all merges, walk the entire tree and at
   every node, merge any direct children sharing a normalized name into one (handles
   both cross-page duplicates and any duplicates that arise from a single page's own
   HTML having redundant listings).

4. **Trace and resolve the "Public administration" anomaly.** Confirm it isn't
   produced by this pipeline (no source page named `Outline_of_public_administration`
   exists in the 68-page list); if it doesn't reappear after the rebuild, no further
   action needed — it was an artifact of the old scraper output, not this pipeline.

5. **Validate before shipping:**
   - No duplicate normalized sibling names anywhere in the output tree (automated
     check).
   - No single branch whose node count is wildly disproportionate to what its source
     page(s) actually contain (spot-check the largest branches against their source
     pages).
   - Spot-check 5-6 domains/branches against their live Wikipedia outline pages for
     obvious omissions.
   - Total node count and per-domain counts reported for a final sanity read (not a
     hard target — correctness matters more than hitting exactly 6,806).

## Output

Same compact data format the app already consumes, so `index.html` needs no format
changes for this phase:
- `taxonomy.json` — full nested tree (name, sources, children).
- `tree-data.js` — compact `RAW_TREE` format (`n`/`u`/`c` keys) that `index.html`
  expands at load time.
- `flat-data.js` — compact `RAW_FLAT` format (name/path/url/depth) for search.
- `README.md` — update the stated total/structure numbers to match the corrected tree.

## Testing plan

- Automated dedup-check script: walk the final tree, assert no parent has two
  children with the same normalized name.
- Automated anomaly-check: flag any node whose child count is > 3x the median for
  sibling nodes at the same depth, for manual review.
- Manual spot-checks against live Wikipedia for a handful of domains (Natural
  science, Formal science — the two flagged as suspiciously shallow — plus 2-3
  others).
- Load the rebuilt `index.html` locally and confirm the tree renders, search works,
  and node counts look sane in the UI.
