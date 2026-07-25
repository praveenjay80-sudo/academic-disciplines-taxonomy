# Learning Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fifth "Path" mode to `index.html` that, given a target topic and optional background, builds one continuous learning path — a grounded LLM-generated prerequisite chain, through the target (a real tree node when it resolves), to the target's real frontier children — eagerly generating Key Questions per stage while reusing all existing per-node generation/render machinery unchanged for deep dives.

**Architecture:** Single-file vanilla JS app (unchanged pattern). New pure helpers (`normalizeForMatch`, `findNodeInFieldTrees`) locate a topic in the already-loaded real trees. A new grounded prompt (`buildPrerequisiteChainPrompt`) generates the prerequisite side. Every resolved stage — prerequisite, target, or frontier — maps to exactly the same node-record shape/cache (`dbGet`/`dbPut` keyed by `pathKey`) already used everywhere else in the app; no parallel caching scheme. A new path-level cache (new IndexedDB store `paths`) stores just the resolved stage list so revisiting a target+background is instant. Per-stage Key Questions reuse `buildKeyQuestionsPrompt`/`callOpenRouter` unchanged, fired in parallel across stages. Deep-dive links (reading lists, Research Questions, Paradigms) reuse the existing single-node content pane by switching `currentNode`/`currentPath` — zero changes to `generateReadingListForQuestion`, `generateResearchQuestionsForCurrentNode`, `generateLiteratureForResearchQuestion`, `generateParadigmsForCurrentNode`, or their render counterparts.

**Tech Stack:** Vanilla JS (ES2020+), `fetch` for OpenRouter + Wikipedia APIs, `indexedDB` for caching. No test framework in this repo — pure logic functions are verified with standalone `node` scripts run from the scratchpad directory; DOM/network-dependent behavior is verified manually in a browser.

## Global Constraints

- No refactor of `generateKeyQuestionsForCurrentNode`, `generateReadingListForQuestion`, `generateResearchQuestionsForCurrentNode`, `generateLiteratureForResearchQuestion`, `generateParadigmsForCurrentNode`, `selectFieldTreeNode`, `generateChildren`, or their `render*` counterparts (per spec Non-goals) — deep-dive interactions reuse them exactly as they exist today by switching the global `currentNode`/`currentPath`.
- Every path stage (prerequisite, target, or frontier) is cached as a normal node `record` via the existing `dbGet(pathKey(path))`/`dbPut` — no duplicate per-stage content cache (per spec Architecture point 4).
- Frontier stages = the target's real direct children, shown unfiltered, one level only (per spec Non-goals — no LLM curation, no deeper walk).
- "What you already know" (background) never hides/skips a prerequisite stage — every genuine prerequisite still appears; background only affects explanation tone/depth (per spec Non-goals).
- Ancestors in the real tree are NOT used as prerequisites — the prerequisite chain is always LLM-generated and grounded, independent of tree parent/child structure (per spec Architecture point 2 — this was a deliberate correction during design, not an oversight).
- All model-generated text placed into `innerHTML` must go through `escHtml` (existing convention, applies to all new render code in this plan).
- Single static HTML file, vanilla JS, no framework, no build step (unchanged from existing repo pattern).

---

### Task 1: Pure helpers — real-tree node search + prerequisite-chain prompt

**Files:**
- Modify: `C:\Users\prave\Projects\academic-disciplines-taxonomy\index.html`
- Test (scratch, not committed): `C:\Users\prave\AppData\Local\Temp\claude\C--WINDOWS-system32\4b00f37f-c664-49c8-beed-c8ad39d2a6d4\scratchpad\test-path-helpers.mjs`

**Interfaces:**
- Consumes: nothing (pure functions).
- Produces: `normalizeForMatch(s)` → lowercased/trimmed string; `findNodeInFieldTrees(fieldTreesData, name)` → `{fieldKey, path, node} | null`, where `fieldTreesData` is `{fieldKey: [topNode, ...]}` (same shape as `FIELD_TREES[key].data`); `buildPrerequisiteChainPrompt(topic, grounding, background)` → prompt string. Used by Task 2 (`pathCacheKey`) and Task 4 (`buildLearningPath`).

This task is purely additive — does not touch any existing function. The app is unaffected until Task 3+ wire these in.

- [ ] **Step 1: Insert `normalizeForMatch` and the tree-search helpers**

Find this exact text:

```javascript
function countFieldNodes(nodes) {
  return nodes.reduce((sum, n) => sum + 1 + countFieldNodes(n.c || []), 0);
}

function renderFieldTreeNode(fieldKey, node, path, depth) {
```

Replace with:

```javascript
function countFieldNodes(nodes) {
  return nodes.reduce((sum, n) => sum + 1 + countFieldNodes(n.c || []), 0);
}

// ============================================================
// LEARNING PATH: real-tree node search
// ============================================================
function normalizeForMatch(s) {
  return (s || '').trim().toLowerCase();
}

function findNodeInTree(nodes, targetLower, ancestorPath) {
  for (const node of nodes) {
    const path = [...ancestorPath, node.n];
    if (normalizeForMatch(node.n) === targetLower) return { path, node };
    if (Array.isArray(node.c) && node.c.length) {
      const found = findNodeInTree(node.c, targetLower, path);
      if (found) return found;
    }
  }
  return null;
}

function findNodeInFieldTrees(fieldTreesData, name) {
  const targetLower = normalizeForMatch(name);
  for (const fieldKey of Object.keys(fieldTreesData)) {
    const found = findNodeInTree(fieldTreesData[fieldKey] || [], targetLower, []);
    if (found) return { fieldKey, path: found.path, node: found.node };
  }
  return null;
}

function renderFieldTreeNode(fieldKey, node, path, depth) {
```

- [ ] **Step 2: Insert `buildPrerequisiteChainPrompt`**

Find this exact text (the end of `buildParadigmsPrompt`, right before `extractJson`):

```javascript
Only include entries if the field genuinely has distinct competing paradigms/schools of thought; if it
doesn't (e.g. a narrow technical topic), return an empty array rather than inventing false divisions.`;
}

function extractJson(text) {
```

Replace with:

```javascript
Only include entries if the field genuinely has distinct competing paradigms/schools of thought; if it
doesn't (e.g. a narrow technical topic), return an empty array rather than inventing false divisions.`;
}

function buildPrerequisiteChainPrompt(topic, grounding, background) {
  const backgroundBlock = (background && background.trim())
    ? `The learner has told you what they already know: "${background.trim()}"\nStill list the FULL genuine prerequisite chain — do not omit or skip a real prerequisite just because it overlaps with this. Just keep the "description" for any prerequisite substantially covered by what they already know appropriately brief (a short acknowledgement is fine) rather than explaining it from scratch.`
    : `No background was given — write each description assuming the learner has none of the prerequisites yet.`;

  return `You are building the genuine PEDAGOGICAL prerequisite chain for learning "${topic}" from zero —
the real sequence of topics a learner needs, roughly foundational-to-advanced, ending JUST BEFORE
"${topic}" itself (do not include "${topic}" as one of the prerequisites).

${groundingBlockFor(grounding)}
${backgroundBlock}

This is a LEARNING/PEDAGOGICAL order, not a library-classification hierarchy — do not just list broader
subject categories "${topic}" happens to be filed under; list what someone genuinely needs to have
learned first to understand "${topic}".

Return ONLY a single JSON object (no markdown fences, no commentary) with this exact shape:

{
  "prerequisites": [
    {"name": "Clean short topic name", "description": "1-2 sentences: what this covers and why it's needed before ${JSON.stringify(topic)}"}
  ]
}

Order matters — earliest/most foundational first. Include every genuine prerequisite, but do not pad
with near-duplicates or overly narrow sub-steps; each entry should be a real, recognizable topic in its
own right (the kind of thing that could itself be a subject heading), not a granular lesson-plan step.`;
}

function extractJson(text) {
```

- [ ] **Step 3: Write a standalone node test**

Create `test-path-helpers.mjs` in the scratchpad directory:

```javascript
function normalizeForMatch(s) {
  return (s || '').trim().toLowerCase();
}

function findNodeInTree(nodes, targetLower, ancestorPath) {
  for (const node of nodes) {
    const path = [...ancestorPath, node.n];
    if (normalizeForMatch(node.n) === targetLower) return { path, node };
    if (Array.isArray(node.c) && node.c.length) {
      const found = findNodeInTree(node.c, targetLower, path);
      if (found) return found;
    }
  }
  return null;
}

function findNodeInFieldTrees(fieldTreesData, name) {
  const targetLower = normalizeForMatch(name);
  for (const fieldKey of Object.keys(fieldTreesData)) {
    const found = findNodeInTree(fieldTreesData[fieldKey] || [], targetLower, []);
    if (found) return { fieldKey, path: found.path, node: found.node };
  }
  return null;
}

function groundingBlockFor(grounding) {
  return grounding ? 'grounded' : 'ungrounded';
}

function buildPrerequisiteChainPrompt(topic, grounding, background) {
  const backgroundBlock = (background && background.trim())
    ? `The learner has told you what they already know: "${background.trim()}"\nStill list the FULL genuine prerequisite chain.`
    : `No background was given.`;
  return `Prerequisite chain for "${topic}". ${groundingBlockFor(grounding)} ${backgroundBlock} Return ONLY a single JSON object with "prerequisites".`;
}

function assertEqual(actual, expected, label) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.error('FAIL:', label, '\n  got:', JSON.stringify(actual), '\n  want:', JSON.stringify(expected));
    process.exitCode = 1;
  } else {
    console.log('PASS:', label);
  }
}
function assertIncludes(haystack, needle, label) {
  if (!haystack.includes(needle)) {
    console.error('FAIL:', label, '\n  expected to find:', JSON.stringify(needle));
    process.exitCode = 1;
  } else {
    console.log('PASS:', label);
  }
}

assertEqual(normalizeForMatch('  Quantum Mechanics  '), 'quantum mechanics', 'normalizeForMatch trims and lowercases');

// Matches the REAL shape of math-tree.json/physics-tree.json/cs-tree.json:
// field.data is an array of top-level topic nodes directly (e.g. real PhySH
// top categories) — there is no synthetic wrapper node literally named
// "Physics"/"Mathematics". findNodeInFieldTrees()'s returned `path` is
// therefore just the in-tree node names, with NO field label prepended;
// callers that need the label (to match selectFieldTreeNode()'s cache-key
// convention) prepend FIELD_TREES[fieldKey].label themselves.
const fixtureTree = {
  physics: [
    { n: 'Quantum information, science, and technology', c: [
      { n: 'Quantum mechanics', c: [
        { n: 'Quantum computing', c: [] },
        { n: 'Quantum field theory', c: [] },
      ] },
    ] },
  ],
  math: [
    { n: 'Calculus', c: [] },
  ],
};

const hit = findNodeInFieldTrees(fixtureTree, 'quantum mechanics');
assertEqual(hit.fieldKey, 'physics', 'finds node in correct field');
assertEqual(hit.path, ['Quantum information, science, and technology', 'Quantum mechanics'], 'finds correct full path, with NO field label prepended');
assertEqual(hit.node.c.map(c => c.n), ['Quantum computing', 'Quantum field theory'], 'returns the matched node with its real children');

const hit2 = findNodeInFieldTrees(fixtureTree, 'Calculus');
assertEqual(hit2.fieldKey, 'math', 'finds top-level node in a different field');

const miss = findNodeInFieldTrees(fixtureTree, 'nonexistent topic xyz');
assertEqual(miss, null, 'returns null for unmatched topic');

const prompt1 = buildPrerequisiteChainPrompt('quantum mechanics', null, '');
assertIncludes(prompt1, 'quantum mechanics', 'prompt includes topic');
assertIncludes(prompt1, 'No background was given', 'prompt uses no-background branch when background is empty');

const prompt2 = buildPrerequisiteChainPrompt('quantum mechanics', null, 'I know calculus');
assertIncludes(prompt2, 'I know calculus', 'prompt includes background when given');
assertIncludes(prompt2, 'FULL genuine prerequisite chain', 'prompt instructs not to skip prerequisites even with background');
```

- [ ] **Step 4: Run the test**

Run: `node "C:\Users\prave\AppData\Local\Temp\claude\C--WINDOWS-system32\4b00f37f-c664-49c8-beed-c8ad39d2a6d4\scratchpad\test-path-helpers.mjs"`

Expected: nine `PASS:` lines, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "Add real-tree node search helpers and prerequisite-chain prompt"
```

---

### Task 2: Path-level IndexedDB cache

**Files:**
- Modify: `C:\Users\prave\Projects\academic-disciplines-taxonomy\index.html`

**Interfaces:**
- Consumes: `normalizeForMatch` (Task 1).
- Produces: `pathCacheKey(target, background)` → string; `dbGetPath(key)` → `Promise<record|null>`; `dbPutPath(record)` → `Promise<void>`. Used by Task 4.

Bumps the IndexedDB version from 1 to 2 to add a new `paths` object store, alongside the existing `nodes` store (untouched, no data migration needed — `onupgradeneeded` only adds the new store).

- [ ] **Step 1: Bump DB version and add the `paths` store**

Find this exact text:

```javascript
function getDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open('academic_explorer', 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('nodes')) {
        db.createObjectStore('nodes', { keyPath: 'path' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}
```

Replace with:

```javascript
function getDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open('academic_explorer', 2);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('nodes')) {
        db.createObjectStore('nodes', { keyPath: 'path' });
      }
      if (!db.objectStoreNames.contains('paths')) {
        db.createObjectStore('paths', { keyPath: 'key' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}
```

- [ ] **Step 2: Add `pathCacheKey`/`dbGetPath`/`dbPutPath`**

Find this exact text:

```javascript
async function dbGetAll() {
  const db = await getDb();
  return new Promise((resolve) => {
    const tx = db.transaction('nodes', 'readonly');
    const req = tx.objectStore('nodes').getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => resolve([]);
  });
}
```

Replace with:

```javascript
async function dbGetAll() {
  const db = await getDb();
  return new Promise((resolve) => {
    const tx = db.transaction('nodes', 'readonly');
    const req = tx.objectStore('nodes').getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => resolve([]);
  });
}

function pathCacheKey(target, background) {
  return normalizeForMatch(target) + '::' + normalizeForMatch(background);
}

async function dbGetPath(key) {
  const db = await getDb();
  return new Promise((resolve) => {
    const tx = db.transaction('paths', 'readonly');
    const req = tx.objectStore('paths').get(key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => resolve(null);
  });
}

async function dbPutPath(record) {
  const db = await getDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('paths', 'readwrite');
    tx.objectStore('paths').put(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
```

- [ ] **Step 3: Manual verification in browser devtools**

Open `index.html` in a browser (serve via a local static server, e.g. `python -m http.server` or `node`-based one-liner, from the repo root — it needs `math-tree.json`/`physics-tree.json`/`cs-tree.json` reachable by relative fetch, so opening the file directly via `file://` will NOT work for this app, unlike the single-file apps in other repos). Open devtools console and run:

```javascript
await dbPutPath({ key: pathCacheKey('Quantum mechanics', ''), stages: [{ name: 'test' }] });
await dbGetPath(pathCacheKey('Quantum mechanics', ''));
```

Expected: second call returns `{key: 'quantum mechanics::', stages: [{name: 'test'}]}`. Then confirm the existing `nodes` store still works unaffected: `await dbPut({path: 'Test', name: 'Test'}); await dbGet('Test');` should still return the record (confirms the version bump didn't break the existing store).

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "Add path-level IndexedDB cache (paths store, DB v2)"
```

---

### Task 3: Path mode UI scaffold

**Files:**
- Modify: `C:\Users\prave\Projects\academic-disciplines-taxonomy\index.html`

**Interfaces:**
- Consumes: nothing new (pure UI scaffold).
- Produces: a "🧭 Learning Path" tab in the mode switcher; `renderPathForm()` (renders the empty target/background form into `#content`); wiring in `switchMainTab` for `tab === 'path'`. Used by Task 4 (`onPathSubmit` will be wired to the form's submit button).

Purely additive to the UI — the target/background inputs don't do anything yet beyond existing (a stub `onPathSubmit` that will be replaced in Task 4). The app's other modes are unaffected.

- [ ] **Step 1: Add CSS for the path form and timeline**

Find this exact text:

```css
  .questions-block { margin-bottom: 20px; }
  .questions-block h4 { color: var(--purple); font-size: 0.9em; margin-bottom: 8px; }
  .question-item { margin-bottom: 8px; padding: 10px 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; }
  .question-item .q { color: var(--text); font-weight: 600; font-size: 0.86em; }
  .question-item .why { color: var(--muted); font-size: 0.78em; margin-top: 2px; }
```

Replace with:

```css
  .questions-block { margin-bottom: 20px; }
  .questions-block h4 { color: var(--purple); font-size: 0.9em; margin-bottom: 8px; }
  .question-item { margin-bottom: 8px; padding: 10px 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; }
  .question-item .q { color: var(--text); font-weight: 600; font-size: 0.86em; }
  .question-item .why { color: var(--muted); font-size: 0.78em; margin-top: 2px; }
  .path-form { max-width: 520px; }
  .path-form label { display: block; color: var(--muted); font-size: 0.8em; margin: 14px 0 4px; }
  .path-form input[type="text"] { width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); padding: 8px 10px; font-size: 0.9em; }
  .path-timeline { max-width: 760px; margin-top: 8px; }
  .path-stage { position: relative; padding: 0 0 24px 28px; border-left: 2px solid var(--border); }
  .path-stage:last-child { border-left-color: transparent; padding-bottom: 0; }
  .path-stage .marker { position: absolute; left: -7px; top: 2px; width: 12px; height: 12px; border-radius: 50%; background: var(--bg); border: 2px solid var(--muted); }
  .path-stage.target .marker { background: var(--accent); border-color: var(--accent); width: 16px; height: 16px; left: -9px; }
  .path-stage .stage-name { color: var(--text); font-weight: 600; font-size: 0.95em; }
  .path-stage.target .stage-name { color: var(--accent); font-size: 1.05em; }
  .path-stage .stage-desc { color: var(--muted); font-size: 0.82em; margin-top: 2px; max-width: 640px; }
  .path-stage .stage-actions { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
  .path-stage-kind { color: var(--muted); font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.04em; }
```

- [ ] **Step 2: Add "Learning Path" to the tab list**

Find this exact text:

```javascript
  const tabs = [
    { key: 'explore', label: '🔍 Explore any topic' },
    { key: 'math', label: 'Mathematics' },
    { key: 'physics', label: 'Physics' },
    { key: 'cs-theory', label: 'Computer Science' },
    { key: 'philosophy', label: 'Philosophy', disabled: true },
  ];
```

Replace with:

```javascript
  const tabs = [
    { key: 'explore', label: '🔍 Explore any topic' },
    { key: 'math', label: 'Mathematics' },
    { key: 'physics', label: 'Physics' },
    { key: 'cs-theory', label: 'Computer Science' },
    { key: 'philosophy', label: 'Philosophy', disabled: true },
    { key: 'path', label: '🧭 Learning Path' },
  ];
```

- [ ] **Step 3: Wire `switchMainTab` for the `path` tab and add `renderPathForm`**

Find this exact text:

```javascript
async function switchMainTab(tab) {
  activeMainTab = tab;
  renderFieldTabs();
  const exploreSidebar = document.getElementById('exploreSidebar');
  const fieldSidebar = document.getElementById('fieldTreeSidebar');
  if (tab === 'explore') {
    exploreSidebar.style.display = '';
    fieldSidebar.style.display = 'none';
    document.getElementById('content').innerHTML = currentNode && !currentNode.isStaticTree
      ? document.getElementById('content').innerHTML
      : '<div class="empty-state"><h2>Pick a starting point</h2><p>Type a topic, or click one of the domains on the left.</p></div>';
    return;
  }
  exploreSidebar.style.display = 'none';
  fieldSidebar.style.display = '';
  document.getElementById('fieldTreeFilter').value = '';
  await loadFieldTree(tab);
  renderFieldTreeSidebar(tab);
  document.getElementById('content').innerHTML = `<div class="empty-state"><h2>${escHtml(FIELD_TREES[tab].label)}</h2><p>Click any topic on the left to see its key questions and reading list.</p></div>`;
}
```

Replace with:

```javascript
async function switchMainTab(tab) {
  activeMainTab = tab;
  renderFieldTabs();
  const exploreSidebar = document.getElementById('exploreSidebar');
  const fieldSidebar = document.getElementById('fieldTreeSidebar');
  if (tab === 'explore') {
    exploreSidebar.style.display = '';
    fieldSidebar.style.display = 'none';
    document.getElementById('content').innerHTML = currentNode && !currentNode.isStaticTree
      ? document.getElementById('content').innerHTML
      : '<div class="empty-state"><h2>Pick a starting point</h2><p>Type a topic, or click one of the domains on the left.</p></div>';
    return;
  }
  if (tab === 'path') {
    exploreSidebar.style.display = 'none';
    fieldSidebar.style.display = 'none';
    renderPathForm();
    return;
  }
  exploreSidebar.style.display = 'none';
  fieldSidebar.style.display = '';
  document.getElementById('fieldTreeFilter').value = '';
  await loadFieldTree(tab);
  renderFieldTreeSidebar(tab);
  document.getElementById('content').innerHTML = `<div class="empty-state"><h2>${escHtml(FIELD_TREES[tab].label)}</h2><p>Click any topic on the left to see its key questions and reading list.</p></div>`;
}

function renderPathForm() {
  document.getElementById('content').innerHTML = `
    <div class="node-header"><h2>🧭 Learning Path</h2></div>
    <p class="node-desc">Enter a topic and (optionally) what you already know — this builds one continuous
    path from genuine prerequisites through the topic to its real research-frontier specializations.</p>
    <div class="path-form">
      <label>Target topic</label>
      <input type="text" id="pathTargetInput" placeholder="e.g. quantum mechanics" />
      <label>What you already know (optional)</label>
      <input type="text" id="pathBackgroundInput" placeholder="e.g. I know calculus" />
      <div style="margin-top:16px"><button class="btn btn-primary" onclick="onPathSubmit()">Build path</button></div>
    </div>
  `;
}

function onPathSubmit() {
  const target = document.getElementById('pathTargetInput').value.trim();
  if (!target) return;
  document.getElementById('content').innerHTML = `<div class="node-header"><h2>🧭 Learning Path</h2></div><div class="loading">⏳ Path generation not implemented yet (Task 4).</div>`;
}
```

- [ ] **Step 4: Manual verification in browser**

Serve the repo root with a local static server (e.g. `node -e "require('http').createServer((req,res)=>{const fs=require('fs'),path=require('path');const p=path.join(process.cwd(),req.url.split('?')[0]);fs.readFile(p,(e,d)=>{if(e){res.writeHead(404);res.end('nf');return;}res.writeHead(200);res.end(d);});}).listen(8934)"` from the repo root), open `http://localhost:8934/index.html`. Click the "🧭 Learning Path" tab. Expected: sidebar disappears, content shows the target/background form. Type a topic, click "Build path" — expected: shows the Task-4-placeholder loading message (confirms wiring works; real generation lands in Task 4).

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "Add Learning Path mode UI scaffold (tab, form, empty wiring)"
```

---

### Task 4: Path resolution and stage assembly

**Files:**
- Modify: `C:\Users\prave\Projects\academic-disciplines-taxonomy\index.html`

**Interfaces:**
- Consumes: `findNodeInFieldTrees`, `buildPrerequisiteChainPrompt`, `normalizeForMatch` (Task 1); `pathCacheKey`, `dbGetPath`, `dbPutPath` (Task 2); `renderPathForm` (Task 3, will be superseded by `onPathSubmit`'s real implementation); `loadFieldTree`, `FIELD_TREES`, `requireApiKey`, `getSelectedModel`, `callOpenRouter`, `fetchWikipediaGrounding`, `escHtml` (existing, unchanged).
- Produces: `async function buildLearningPath(target, background)` → resolves and caches the stage list, calls `renderPathTimeline` (stub from this task, real implementation in Task 5). Replaces Task 3's placeholder `onPathSubmit`.

A stage descriptor has this shape: `{ name, description, kind, isRealNode, fieldKey, path }` where `kind` is `'prerequisite' | 'target' | 'frontier'`, `path` is the array used as this stage's own node-record path (real tree path if `isRealNode`, else `[name]` — same convention Explore mode uses for a bare topic).

- [ ] **Step 1: Replace the Task 3 placeholder `onPathSubmit` with real resolution + assembly**

Find this exact text:

```javascript
function onPathSubmit() {
  const target = document.getElementById('pathTargetInput').value.trim();
  if (!target) return;
  document.getElementById('content').innerHTML = `<div class="node-header"><h2>🧭 Learning Path</h2></div><div class="loading">⏳ Path generation not implemented yet (Task 4).</div>`;
}
```

Replace with:

```javascript
function onPathSubmit() {
  const target = document.getElementById('pathTargetInput').value.trim();
  const background = document.getElementById('pathBackgroundInput').value.trim();
  if (!target) return;
  buildLearningPath(target, background);
}

async function loadAllFieldTreesData() {
  const data = {};
  for (const key of Object.keys(FIELD_TREES)) {
    await loadFieldTree(key);
    data[key] = FIELD_TREES[key].data;
  }
  return data;
}

function renderPathLoading(msg) {
  document.getElementById('content').innerHTML = `<div class="node-header"><h2>🧭 Learning Path</h2></div><div class="loading">⏳ ${escHtml(msg)}</div>`;
}

function renderPathError(msg, target, background) {
  document.getElementById('content').innerHTML = `<div class="node-header"><h2>🧭 Learning Path</h2></div>
    <div class="error">❌ ${escHtml(msg)}</div>
    <div style="margin-top:12px"><button class="btn" onclick="buildLearningPath(${escAttr(JSON.stringify(target))}, ${escAttr(JSON.stringify(background))})">Retry</button></div>`;
}

async function buildLearningPath(target, background) {
  const apiKey = requireApiKey();
  if (!apiKey) return;
  const model = getSelectedModel();

  renderPathLoading('Checking cache…');
  const cacheKey = pathCacheKey(target, background);
  const cached = await dbGetPath(cacheKey);
  if (cached) {
    renderPathTimeline(cached.stages, target, background);
    return;
  }

  renderPathLoading('Locating "' + target + '" in the real classification trees…');
  const fieldTreesData = await loadAllFieldTreesData();
  const targetMatch = findNodeInFieldTrees(fieldTreesData, target);

  let targetGrounding = null;
  try { targetGrounding = await fetchWikipediaGrounding(target); } catch (e) { /* optional */ }

  renderPathLoading('Working out the prerequisite chain for "' + target + '"…');
  let prereqParsed;
  try {
    prereqParsed = await callOpenRouter(apiKey, model, buildPrerequisiteChainPrompt(target, targetGrounding, background), 6000);
  } catch (e) {
    renderPathError('Prerequisite chain failed: ' + e.message, target, background);
    return;
  }
  const prerequisites = Array.isArray(prereqParsed.prerequisites) ? prereqParsed.prerequisites : [];

  // NOTE: findNodeInFieldTrees()'s returned `path` does NOT include the
  // field label (e.g. "Physics") — it matches renderFieldTreeNode()'s path
  // convention. selectFieldTreeNode() (existing, unchanged) builds its own
  // node-record cache key as pathKey([fieldLabel, ...path]) — WITH the
  // label. Every real-node stage below prepends FIELD_TREES[...].label so
  // ensureStageNodeRecord()'s pathKey(stage.path) lands on the exact same
  // cache key selectFieldTreeNode() would use for that node, and so a
  // stage generated here is the same cached record you'd get browsing to
  // it directly via the sidebar tree (per spec Architecture point 4).
  const stages = [];
  for (const p of prerequisites) {
    const match = findNodeInFieldTrees(fieldTreesData, p.name);
    stages.push({
      name: p.name,
      description: p.description || '',
      kind: 'prerequisite',
      isRealNode: !!match,
      fieldKey: match ? match.fieldKey : null,
      path: match ? [FIELD_TREES[match.fieldKey].label, ...match.path] : [p.name],
    });
  }

  stages.push({
    name: target,
    description: '',
    kind: 'target',
    isRealNode: !!targetMatch,
    fieldKey: targetMatch ? targetMatch.fieldKey : null,
    path: targetMatch ? [FIELD_TREES[targetMatch.fieldKey].label, ...targetMatch.path] : [target],
  });

  if (targetMatch) {
    const children = targetMatch.node.c || [];
    const targetFullPath = [FIELD_TREES[targetMatch.fieldKey].label, ...targetMatch.path];
    for (const c of children) {
      stages.push({
        name: c.n,
        description: '',
        kind: 'frontier',
        isRealNode: true,
        fieldKey: targetMatch.fieldKey,
        path: [...targetFullPath, c.n],
      });
    }
  }

  await dbPutPath({ key: cacheKey, target, background, stages, generatedAt: Date.now() });
  renderPathTimeline(stages, target, background);
}
```

- [ ] **Step 2: Add a temporary stub for `renderPathTimeline` (real implementation lands in Task 5)**

Find this exact text (the end of the function you just inserted, immediately after `renderPathTimeline(stages, target, background);` inside `buildLearningPath` — i.e. add this new function right after `buildLearningPath`'s closing `}`):

```javascript
  await dbPutPath({ key: cacheKey, target, background, stages, generatedAt: Date.now() });
  renderPathTimeline(stages, target, background);
}
```

Replace with:

```javascript
  await dbPutPath({ key: cacheKey, target, background, stages, generatedAt: Date.now() });
  renderPathTimeline(stages, target, background);
}

function renderPathTimeline(stages, target, background) {
  // Stub — replaced with the real timeline renderer in Task 5.
  document.getElementById('content').innerHTML = `<div class="node-header"><h2>🧭 Learning Path</h2></div>
    <p class="node-desc">Resolved ${stages.length} stages for "${escHtml(target)}" (rendering lands in Task 5). Stage order: ${stages.map(s => escHtml(s.name) + ' [' + s.kind + (s.isRealNode ? ', real' : ', llm') + ']').join(' → ')}</p>`;
}
```

- [ ] **Step 3: Manual verification (structural, no real API key needed for the wiring; content quality needs Task 6's live check)**

Serve the repo root locally (as in Task 3 Step 4). Open the Path tab, enter target "Quantum mechanics" (a real PhySH node) and a fake/invalid API key, click "Build path". Expected: loading messages update ("Checking cache…" → "Locating…" → "Working out the prerequisite chain…"), then the request fails with a 401/invalid-key error and `renderPathError` shows an inline error + Retry button (confirms the failure path doesn't crash). Confirm clicking Retry re-attempts `buildLearningPath` with the same target/background.

If you have a real OpenRouter key available, you may also run it once for real here to sanity-check the stub output shows a sensible stage list (e.g. Calculus → Linear algebra → ... → Quantum mechanics [target] → Quantum computing, Quantum field theory, ... [frontier, real]) — but full verification of this is Task 6's job; do not block this task on having a key.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "Add path resolution and stage assembly (buildLearningPath)"
```

---

### Task 5: Per-stage Key Questions generation, timeline rendering, and deep-dive jump-in

**Files:**
- Modify: `C:\Users\prave\Projects\academic-disciplines-taxonomy\index.html`

**Interfaces:**
- Consumes: `buildKeyQuestionsPrompt` (existing — gains an optional 4th `background` parameter in this task, backward-compatible), `callOpenRouter`, `dbGet`, `dbPut`, `pathKey`, `fetchWikipediaGrounding`, `requireApiKey`, `getSelectedModel`, `escHtml`, `escAttr`, `QUESTION_LEVELS`, `renderKeyQuestionsHtml`-style rendering conventions (existing).
- Produces: `renderPathTimeline` (real implementation, replaces Task 4's stub); `ensureStageNodeRecord(stage)`; `generateStageKeyQuestions(stage, apiKey, model, background)`; `openPathStageNode(stage)` (jump-in navigation, used by deep-dive links). This is the last task that changes generation/render behavior — Task 6 is verification only.

- [ ] **Step 1: Give `buildKeyQuestionsPrompt` an optional background parameter (backward-compatible)**

Find this exact text:

```javascript
function buildKeyQuestionsPrompt(topic, path, grounding) {
  const breadcrumb = path.join(' > ');
  return `You are explaining the field "${topic}" (full path: ${breadcrumb}) to someone who has never
studied it, by identifying the real questions it is trying to answer.

${groundingBlockFor(grounding)}
```

Replace with:

```javascript
function buildKeyQuestionsPrompt(topic, path, grounding, background) {
  const breadcrumb = path.join(' > ');
  const backgroundNote = (background && background.trim())
    ? `\nThe learner has told you what they already know: "${background.trim()}" — keep beginner-level explanations appropriately brief for anything this background already covers, rather than explaining it from absolute scratch. Do not omit any question tier because of this.\n`
    : '';
  return `You are explaining the field "${topic}" (full path: ${breadcrumb}) to someone who has never
studied it, by identifying the real questions it is trying to answer.

${groundingBlockFor(grounding)}
${backgroundNote}
```

- [ ] **Step 2: Add `ensureStageNodeRecord` and `generateStageKeyQuestions`**

Find this exact text (the end of `buildLearningPath`'s stub-replaced companion — the `renderPathTimeline` stub from Task 4):

```javascript
function renderPathTimeline(stages, target, background) {
  // Stub — replaced with the real timeline renderer in Task 5.
  document.getElementById('content').innerHTML = `<div class="node-header"><h2>🧭 Learning Path</h2></div>
    <p class="node-desc">Resolved ${stages.length} stages for "${escHtml(target)}" (rendering lands in Task 5). Stage order: ${stages.map(s => escHtml(s.name) + ' [' + s.kind + (s.isRealNode ? ', real' : ', llm') + ']').join(' → ')}</p>`;
}
```

Replace with:

```javascript
async function ensureStageNodeRecord(stage) {
  const key = pathKey(stage.path);
  const existing = await dbGet(key);
  if (existing) return existing;

  let grounding = null;
  try { grounding = await fetchWikipediaGrounding(stage.name); } catch (e) { /* optional */ }

  const record = {
    path: key,
    name: stage.name,
    description: '',
    children: [],
    groundingSource: grounding,
    generatedAt: Date.now(),
    keyQuestions: null,
    keyQuestionsGenerated: false,
    questionReadingLists: {},
    researchQuestions: null,
    researchQuestionsGenerated: false,
    researchQuestionLiterature: {},
    paradigms: null,
    paradigmsGenerated: false,
  };
  if (stage.isRealNode) {
    record.isStaticTree = true;
    record.fieldKey = stage.fieldKey;
  }
  await dbPut(record);
  return record;
}

async function generateStageKeyQuestions(stage, apiKey, model, background) {
  const record = await ensureStageNodeRecord(stage);
  if (record.keyQuestionsGenerated) return record;
  const parsed = await callOpenRouter(apiKey, model, buildKeyQuestionsPrompt(stage.name, stage.path, record.groundingSource, background), 8000);
  record.keyQuestions = parsed.key_questions || { beginner: [], intermediate: [], advanced: [] };
  record.keyQuestionsGenerated = true;
  record.questionReadingLists = record.questionReadingLists || {};
  await dbPut(record);
  return record;
}

function pathStageDomId(index) {
  return 'path-stage-' + index;
}

async function renderPathTimeline(stages, target, background) {
  const apiKey = requireApiKey();
  if (!apiKey) return;
  const model = getSelectedModel();

  let html = `<div class="node-header"><h2>🧭 Learning Path: ${escHtml(target)}</h2></div><div class="path-timeline">`;
  stages.forEach((stage, i) => {
    html += renderPathStageShell(stage, i);
  });
  html += '</div>';
  document.getElementById('content').innerHTML = html;

  await Promise.all(stages.map((stage, i) => generateAndRenderStage(stage, i, apiKey, model, background)));
}

function renderPathStageShell(stage, index) {
  const kindLabel = stage.kind === 'target' ? 'TARGET' : (stage.kind === 'prerequisite' ? 'PREREQUISITE' : 'FRONTIER / SPECIALIZATION');
  return `<div class="path-stage ${stage.kind === 'target' ? 'target' : ''}" id="${pathStageDomId(index)}">
    <div class="marker"></div>
    <div class="path-stage-kind">${escHtml(kindLabel)}${stage.isRealNode ? ' · real classification node' : ''}</div>
    <div class="stage-name">${escHtml(stage.name)}</div>
    ${stage.description ? `<div class="stage-desc">${escHtml(stage.description)}</div>` : ''}
    <div class="stage-body">⏳ Working out key questions…</div>
  </div>`;
}

async function generateAndRenderStage(stage, index, apiKey, model, background) {
  const el = document.getElementById(pathStageDomId(index));
  try {
    const record = await generateStageKeyQuestions(stage, apiKey, model, background);
    if (!el) return;
    const bodyEl = el.querySelector('.stage-body');
    bodyEl.innerHTML = renderPathStageKeyQuestionsHtml(record, stage);
  } catch (e) {
    if (!el) return;
    const bodyEl = el.querySelector('.stage-body');
    bodyEl.innerHTML = `<div class="error">❌ ${escHtml(e.message)}</div>
      <div style="margin-top:8px"><button class="btn btn-small" onclick="retryPathStage(${index})">Retry</button></div>`;
  }
}

// Stages array must stay reachable for retry — stashed on window since the
// timeline is rebuilt from a single buildLearningPath()/renderPathTimeline()
// call and there is exactly one path visible at a time.
let currentPathStages = null;
let currentPathBackground = '';

function retryPathStage(index) {
  const apiKey = requireApiKey();
  if (!apiKey) return;
  const model = getSelectedModel();
  const stage = currentPathStages[index];
  const el = document.getElementById(pathStageDomId(index));
  if (el) el.querySelector('.stage-body').innerHTML = '⏳ Working out key questions…';
  generateAndRenderStage(stage, index, apiKey, model, currentPathBackground);
}

function renderPathStageKeyQuestionsHtml(record, stage) {
  const counts = QUESTION_LEVELS.map(([lvl]) => (record.keyQuestions && record.keyQuestions[lvl] || []).length);
  let html = renderKeyQuestionsHtml(record);
  html += `<div class="stage-actions">
    <button class="btn btn-small" onclick="openPathStageNode(${escAttr(JSON.stringify(stage))})">Open full view (reading lists, research questions, paradigms) →</button>
  </div>`;
  return html;
}

function openPathStageNode(stage) {
  if (stage.isRealNode) {
    activeMainTab = stage.fieldKey;
    renderFieldTabs();
    document.getElementById('exploreSidebar').style.display = 'none';
    document.getElementById('fieldTreeSidebar').style.display = '';
    selectFieldTreeNode(stage.fieldKey, stage.path.slice(1));
  } else {
    activeMainTab = 'explore';
    renderFieldTabs();
    document.getElementById('exploreSidebar').style.display = '';
    document.getElementById('fieldTreeSidebar').style.display = 'none';
    navigateTo(stage.path);
  }
}
```

- [ ] **Step 3: Stash the resolved stages/background for retry, in `buildLearningPath`**

Find this exact text (inside `buildLearningPath`, both call sites of `renderPathTimeline`):

```javascript
  const cached = await dbGetPath(cacheKey);
  if (cached) {
    renderPathTimeline(cached.stages, target, background);
    return;
  }
```

Replace with:

```javascript
  const cached = await dbGetPath(cacheKey);
  if (cached) {
    currentPathStages = cached.stages;
    currentPathBackground = background;
    renderPathTimeline(cached.stages, target, background);
    return;
  }
```

Then find this exact text (the end of `buildLearningPath`):

```javascript
  await dbPutPath({ key: cacheKey, target, background, stages, generatedAt: Date.now() });
  renderPathTimeline(stages, target, background);
}
```

Replace with:

```javascript
  await dbPutPath({ key: cacheKey, target, background, stages, generatedAt: Date.now() });
  currentPathStages = stages;
  currentPathBackground = background;
  renderPathTimeline(stages, target, background);
}
```

- [ ] **Step 4: Manual verification (fake key — structural only; live content verification is Task 6)**

Serve the repo locally, open the Path tab, submit target "Quantum mechanics" with a fake/invalid key. Expected: timeline renders immediately with all stage shells ("⏳ Working out key questions…"), then each stage independently settles into an inline error + per-stage Retry button as its own call fails (401) — confirm stages don't all wait on each other (i.e. they don't appear to complete in strict serial lock-step; exact timing will vary but there should be no single shared error blocking the whole timeline). Click one stage's Retry — confirm only that stage's body updates.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "Add per-stage Key Questions generation, timeline rendering, and deep-dive jump-in"
```

---

### Task 6: End-to-end live verification

**Files:** None (verification only; if any step fails, fix the responsible function from Tasks 4-5 in this same task and commit the fix).

Requires a real OpenRouter API key. This corresponds to the design spec's 8-step testing list.

- [ ] **Step 1:** Open the Path tab, target "quantum mechanics", no background, submit. Confirm: prerequisite chain generates and renders as an ordered list of stages before the target; target is visually highlighted (filled/larger marker, accent-colored name); frontier stages match "Quantum mechanics"'s actual real children (cross-check by separately browsing to that node in the Physics tab and comparing its child list in the sidebar tree).

- [ ] **Step 2:** Confirm each stage's Key Questions populate independently as they complete (not all waiting on the slowest). Confirm a prerequisite stage that also exists as a real tree node (e.g. "Calculus") is genuinely linked — click its "Open full view" link and confirm it opens the exact same content (from cache) you'd get navigating to that node directly via the Math tab sidebar.

- [ ] **Step 3:** Re-submit the same target with no background. Confirm the path loads instantly from the path-level cache (no re-run of target resolution or the prerequisite-chain call — no new streaming/loading flicker), while each stage's own content still loads correctly from its own node-record cache.

- [ ] **Step 4:** Submit target "quantum mechanics" with background "I know calculus". Confirm the full prerequisite chain still includes every genuine prerequisite stage (nothing hidden), but the Calculus-related stage's explanations are appropriately brief rather than re-explaining from scratch.

- [ ] **Step 5:** Submit a target with no real-tree match (an obscure/invented topic, e.g. "the philosophy of breakfast cereal branding"). Confirm it falls back to Explore-style grounded generation for the prerequisite chain and target, and that there is no frontier section (since `targetMatch` is null, no children are appended) — confirm this doesn't render as a broken/empty-looking section, just fewer stages.

- [ ] **Step 6:** Force a failure in the prerequisite-chain call (temporarily invalid key) — confirm a page-level error + retry (not a partial/broken render), and that retry re-attempts cleanly.

- [ ] **Step 7:** Force a failure in a single stage's Key Questions call in a way that doesn't affect the others (e.g. correct the key back after the initial prerequisite-chain call succeeds, then simulate one stage failing — if this can't be cleanly isolated live, rely on Task 5 Step 4's fake-key structural test as sufficient coverage for this specific point, and note that in the report).

- [ ] **Step 8:** Click a "Open full view" deep-dive link from a frontier stage — confirm it switches to the normal single-node content pane focused on that node (correct field tab active, correct sidebar tree visible, correct node selected/highlighted), identical to navigating there via the sidebar tree directly.
