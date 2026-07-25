# Learning Path — Design

## Summary

A new fifth top-level mode, "Path," alongside the existing Math / Physics / CS / Explore modes. Given a target topic (e.g. "quantum mechanics") and optionally what the user already knows (e.g. "I know calculus"), it generates a single continuous learning path from genuine prerequisites through the target topic to its real research-frontier specializations — reusing the app's existing real-classification data, grounding, and per-node generation functions almost entirely unchanged.

## Goals

- One continuous, ordered path from "zero" (or from whatever the user says they already know) to the target topic to its current research frontier — not a tree to browse node-by-node.
- Grounded, not hallucinated: the target resolves against the real classification trees (MSC/PhySH/CCS) when possible; the prerequisite chain is LLM-generated but grounded against the target's real Wikipedia text; the frontier side is the target's actual real child nodes, not invented ones.
- Reuse everything the app already does well (Key Questions, per-question reading lists, Research Questions + literature, Paradigms) rather than rebuilding parallel machinery.
- The whole path readable as an outline immediately after generation, with depth available on demand per stage.

## Non-goals

- No skipping/hiding of prerequisite stages based on "what you already know" — every stage in the chain still appears; the background text only affects tone/depth of generated explanations (per user decision: keep the full path, adjust explanations, don't collapse nodes).
- No LLM-curated filtering of the frontier side — all of the target's real direct children are shown, unfiltered (per user decision).
- No refactor of the existing single-node generation/render functions (`generateKeyQuestionsForCurrentNode`, `generateReadingListForQuestion`, `generateResearchQuestionsForCurrentNode`, `generateLiteratureForResearchQuestion`, `generateParadigmsForCurrentNode`, and their `render*Html` counterparts) to support multiple simultaneously-expanded stages. They keep operating on the single global `currentNode`/`currentPath`, exactly as today.
- No deep multi-level walk into the frontier side (grandchildren, etc.) — one level of real children only. A stage's own "Research Questions" feature (already built) is what represents "highest research" for that specific node; going deeper into a frontier child just means navigating to it, which the existing app already supports.

## Architecture & data flow

1. **Target resolution.** Search the three loaded real trees (`FIELD_TREES` data already used by the Math/Physics/CS sidebar) for a node whose name matches the submitted target topic (case-insensitive, same normalization style as `onFieldTreeFilter`'s substring match). If found, the target is anchored to that real node (its real path, its real children available for the frontier side). If not found, the target is treated the same way Explore mode treats an arbitrary topic: no real node, grounded via `fetchWikipediaGrounding` only.

2. **Prerequisite chain generation.** One new grounded LLM call, `buildPrerequisiteChainPrompt(topic, grounding, background)`, fed the target's Wikipedia grounding (from `fetchWikipediaGrounding`) and the user's "what you already know" text. Returns an ordered list of genuine pedagogical prerequisites — foundational to advanced, ending just before the target. This is independent of the real tree's parent/ancestor structure (classification nesting is not a reliable proxy for learning order — confirmed and deliberately rejected during design). Each returned prerequisite name is checked against the real trees the same way the target was; if it matches a real node, that stage links to the real node's path.

3. **Frontier side.** If the target resolved to a real node, its direct children (already-loaded real tree data, no API call) become the frontier stages, unfiltered — all of them, in whatever order the real tree lists them. If the target did not resolve to a real node, there is no frontier side (the path ends at the target).

4. **Per-stage Key Questions.** Once the full stage list is known (prerequisites + target + frontier children), fire one `buildKeyQuestionsPrompt` call per stage in parallel (reusing the exact existing prompt/function shape used by `generateKeyQuestionsForCurrentNode`, just invoked in a loop across stages instead of for a single `currentNode`). Each stage's result is stored in that stage's own node `record` (same shape as every other node record in this app: `keyQuestions`, `keyQuestionsGenerated`, `questionReadingLists`, etc.), cached via the existing `dbPut`/`dbGet` keyed by that stage's `pathKey`. This means a stage generated via the Path feature is the *same cached record* you'd get by navigating to that node directly in the Physics/Math/CS tree — no duplicate caching, no divergence.

5. **Path-level cache.** A new cache record (separate store or a prefixed key in the existing store — implementation's choice, but keyed by normalized target + normalized background) stores the resolved stage list itself (ordered array of `{name, path, isRealNode}` stage descriptors) so revisiting the same target+background instantly re-shows the timeline without re-running target resolution or the prerequisite-chain call. Each stage's own content still loads from its own node-record cache as normal.

## UI

- New "Path" tab in the top-level mode switcher, alongside Math / Physics / CS / Explore.
- Two inputs: target topic (text), "what you already know" (text, optional).
- On submit: resolve target → generate prerequisite chain → assemble stage list → render the timeline immediately in a loading state per stage → fire the per-stage Key Questions calls in parallel → each stage's inline Key Questions populate as they complete (not blocking on the slowest one).
- Timeline layout: vertical, ordered top-to-bottom as prerequisites → target (visually highlighted, e.g. filled marker vs. hollow markers for other stages) → frontier children.
- Each stage row: name, one-line status/description, and once generated, its 🌱🌿🌳 Key Questions rendered inline (reusing `renderKeyQuestionsHtml` or an equivalent inline variant).
- Each stage row also has deep-dive links — "Reading list" (per question, once Key Questions exist), "Research Questions", "Paradigms". Clicking any of these does NOT render inline; it calls the existing single-node navigation path (equivalent to `selectFieldTreeNode`/`navigateTo` for that stage's resolved path) and switches the view to the app's normal single-node content pane, exactly as clicking that node in a sidebar tree does today. This is a deliberate reuse decision, not a limitation to fix later — confirmed with the user.
- A stage that failed to generate its Key Questions shows an inline error + a retry affordance scoped to that stage only, not the whole path.

## Prompts

**`buildPrerequisiteChainPrompt(topic, grounding, background)`** (new): given the target topic, its Wikipedia grounding text, and the user's stated background, return the genuine ordered pedagogical prerequisite chain — the sequence of topics a learner would need, roughly foundational-to-advanced, ending just before the target itself. If `background` is non-empty, the prompt should instruct the model to still list the full genuine chain (per Non-goals — no skipping) but keep explanations/descriptions appropriately brief for prerequisites the background suggests the user already has. Returns JSON: `{"prerequisites": [{"name": string, "description": string}]}`.

**Per-stage Key Questions**: no new prompt — reuses `buildKeyQuestionsPrompt(topic, path, grounding)` exactly as it exists today, called once per stage with that stage's own resolved topic/path/grounding. If `background` is relevant to tone (per user's "adjust tone/depth of explanations" decision), thread it into this call too as an additional parameter so beginner-level questions for a stage the user already knows aren't over-explained from scratch.

**Reading lists / Research Questions / literature / Paradigms**: entirely unchanged — invoked exactly as today, once the user clicks into a stage's single-node view.

## Error handling

- Target resolution never "fails" — it either finds a real node or falls back to ungrounded/Explore-style treatment; there's no error state for this step itself.
- Prerequisite-chain call failure: blocks the whole path (no stage list can be assembled without it) — shown as a page-level error with a retry that re-runs just this call (target resolution result is still cached/known, no need to re-resolve).
- A single stage's Key Questions call failure: isolated to that stage's row — inline error + retry button that re-fires only that stage's `buildKeyQuestionsPrompt` call, leaving all other stages' already-generated content untouched.
- Malformed JSON from any of these calls: caught the same way existing calls handle it (via `extractJson`), surfaced as that call's error state rather than crashing the render.

## Testing / verification

Manual (no test framework in this repo, consistent with the existing app):

1. Open the app, go to the Path tab, enter "quantum mechanics" as the target (a real PhySH node) with no background text, submit. Confirm: prerequisite chain generates and renders as an ordered list of stages before the target; target is visually highlighted; frontier stages match "quantum mechanics"'s actual real children in the Physics tree data (spot-check against browsing to that node directly in the Physics tab).
2. Confirm each stage's Key Questions populate independently as they complete (don't all wait for the slowest one) and that a prerequisite stage which also exists as a real tree node is genuinely linked to that real node (clicking its deep-dive link opens the same content you'd get navigating there directly).
3. Re-submit the same target + no background. Confirm the path loads instantly from the path-level cache (no re-run of target resolution or the prerequisite-chain call), while still correctly loading each stage's own cached content.
4. Submit target "quantum mechanics" with background "I know calculus". Confirm the full prerequisite chain still includes all genuine prerequisite stages (none hidden/skipped), but explanations for stages related to calculus are appropriately brief rather than re-explaining from scratch.
5. Submit a target that does not exist in any real tree (an obscure or invented topic). Confirm it falls back to Explore-style grounded generation for the prerequisite chain and target, and that there is no frontier section (or it's clearly marked as unavailable) since there's no real node to pull children from.
6. Force a failure in the prerequisite-chain call (e.g. temporarily invalid API key) — confirm a page-level error + retry, not a partial/broken render.
7. Force a failure in a single stage's Key Questions call (e.g. by triggering it separately) — confirm only that stage shows an error + retry, and other already-generated stages are unaffected.
8. Click a "Research Questions" deep-dive link from a frontier stage — confirm it switches to the normal single-node content pane focused on that node, identical to navigating there via the sidebar tree.
