# Taxonomy Rebuild Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the taxonomy data pipeline so every discipline from the 68+ Wikipedia
"Outline of..." pages is merged into its correct place in the 5-domain tree exactly
once — no duplicate sibling branches, no untraceable anomalous branches — and ship the
corrected `taxonomy.json` / `tree-data.js` / `flat-data.js` to the repo.

**Architecture:** A new self-contained pipeline in `scripts/build_taxonomy.py`: parse
each cached Wikipedia outline page into its own small tree, then merge each page's
tree into the *matching node* inside the `Outline_of_academic_disciplines` skeleton
(found by recursive name search, with a static domain-fallback table for the handful
of pages whose topic name doesn't literally match any existing node), then run a
global recursive dedup pass, then emit the same compact JS/JSON formats `index.html`
already consumes.

**Tech Stack:** Python 3.11 (stdlib `unittest`, `json`, `re`, `urllib`), BeautifulSoup4
(already installed) for HTML parsing.

## Global Constraints

- Source of truth is the 68–72 Wikipedia "Outline of..." pages listed in
  `WIKI_OUTLINE_PAGES` (spec: Wikipedia-outline-only, no OpenAlex/CIP/ANZSRC/MeSH —
  see `docs/superpowers/specs/2026-07-24-taxonomy-rebuild-design.md`, Non-goals).
- No duplicate normalized sibling names anywhere in the final tree (spec: Goal).
- Output formats (`taxonomy.json`, `tree-data.js` `RAW_TREE` shape, `flat-data.js`
  `RAW_FLAT` shape) must stay byte-compatible with what `index.html` already parses,
  since Phase 2 (app rebuild) hasn't happened yet.
- Work happens in `~/Projects/academic-disciplines-taxonomy` (this repo clone), not
  the loose files in the home directory.

---

## File Structure

```
scripts/
  build_taxonomy.py       # pipeline: fetch/cache, parse, merge, dedup, emit outputs
  test_build_taxonomy.py  # unittest tests for parse/merge/dedup/emit functions
  verify_taxonomy.py      # standalone validator: dedup check (hard fail) + anomaly report
  .cache_wiki/             # gitignored raw HTML cache (seeded once from ~/taxonomy_raw)
.gitignore                 # new file: ignore scripts/.cache_wiki/, __pycache__
taxonomy.json               # regenerated
tree-data.js                 # regenerated
flat-data.js                  # regenerated
taxonomy_flat.json            # regenerated (full-key flat export, kept in sync)
README.md                     # stats updated to match rebuilt tree
```

---

### Task 1: Repo scaffold, gitignore, and seeded HTML cache

**Files:**
- Create: `.gitignore`
- Create: `scripts/build_taxonomy.py` (skeleton only — constants and cache I/O, no
  parsing/merge logic yet)

**Interfaces:**
- Produces: `WIKI_OUTLINE_PAGES` (list of 72 page-title strings), `CACHE_DIR` (str
  path constant `scripts/.cache_wiki`), `load_page_html(title) -> str | None` — reads
  from `CACHE_DIR/wiki_<title>.html` if present, else fetches via Wikipedia API
  (action API first, REST API fallback) and caches it, else returns `None`.

- [ ] **Step 1: Create `.gitignore`**

```
scripts/.cache_wiki/
__pycache__/
*.pyc
```

- [ ] **Step 2: Create the cache directory and seed it from the existing local fetch**

```bash
mkdir -p scripts/.cache_wiki
cp /c/Users/prave/taxonomy_raw/wiki_Outline_of_*.html scripts/.cache_wiki/
ls scripts/.cache_wiki | wc -l
```

Expected: `68` (the 68 pages already fetched by the earlier, abandoned pipeline
attempt — reused here so we don't hit Wikipedia unnecessarily).

- [ ] **Step 3: Write `scripts/build_taxonomy.py` skeleton**

```python
#!/usr/bin/env python3
"""Academic Disciplines Taxonomy Builder — Wikipedia Outline pages only.

Parses the 72 "Outline of..." pages, merges each into its matching node inside
the Outline_of_academic_disciplines skeleton (by recursive name search, falling
back to a static domain table when no matching node exists), deduplicates any
remaining same-name siblings, and emits taxonomy.json / tree-data.js /
flat-data.js / taxonomy_flat.json in the exact formats index.html expects.
"""
import json
import os
import re
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, '.cache_wiki')
REPO_DIR = os.path.dirname(SCRIPT_DIR)
os.makedirs(CACHE_DIR, exist_ok=True)

WIKI_OUTLINE_PAGES = sorted([
    'Outline_of_academic_disciplines', 'Outline_of_accounting', 'Outline_of_agriculture',
    'Outline_of_anthropology', 'Outline_of_applied_science', 'Outline_of_archaeology',
    'Outline_of_architecture', 'Outline_of_artificial_intelligence', 'Outline_of_astronomy',
    'Outline_of_biology', 'Outline_of_business', 'Outline_of_chemistry',
    'Outline_of_cognitive_science', 'Outline_of_communication', 'Outline_of_computer_science',
    'Outline_of_cooking', 'Outline_of_cryptography', 'Outline_of_cuisines',
    'Outline_of_culture', 'Outline_of_dance', 'Outline_of_database_concepts',
    'Outline_of_earth_science', 'Outline_of_economics', 'Outline_of_education',
    'Outline_of_energy', 'Outline_of_energy_development', 'Outline_of_energy_storage',
    'Outline_of_engineering', 'Outline_of_film', 'Outline_of_finance',
    'Outline_of_food_preparation', 'Outline_of_formal_science', 'Outline_of_geography',
    'Outline_of_health', 'Outline_of_history', 'Outline_of_journalism',
    'Outline_of_law', 'Outline_of_linguistics', 'Outline_of_literature',
    'Outline_of_logic', 'Outline_of_machine_learning', 'Outline_of_management',
    'Outline_of_marketing', 'Outline_of_mathematics', 'Outline_of_medicine',
    'Outline_of_military_science_and_technology', 'Outline_of_music',
    'Outline_of_natural_science', 'Outline_of_neuroscience', 'Outline_of_nutrition',
    'Outline_of_performing_arts', 'Outline_of_philosophy', 'Outline_of_physical_exercise',
    'Outline_of_physics', 'Outline_of_political_science', 'Outline_of_programming_languages',
    'Outline_of_psychology', 'Outline_of_religion', 'Outline_of_robotics',
    'Outline_of_social_science', 'Outline_of_sociology', 'Outline_of_software_engineering',
    'Outline_of_sports', 'Outline_of_statistics', 'Outline_of_television_broadcasting',
    'Outline_of_the_Internet', 'Outline_of_the_arts', 'Outline_of_the_humanities',
    'Outline_of_the_visual_arts', 'Outline_of_theatre', 'Outline_of_transport',
    'Outline_of_video_games',
])


def _cache_path(title):
    return os.path.join(CACHE_DIR, f'wiki_{title}.html')


def _fetch_wiki_page(title):
    url = f'https://en.wikipedia.org/w/api.php?action=parse&page={title}&format=json&prop=text&redirects=1'
    req = urllib.request.Request(url, headers={'User-Agent': 'TaxonomyRebuild/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return data['parse']['text']['*']
    except Exception:
        return None


def _fetch_wiki_rest(title):
    url = f'https://en.wikipedia.org/api/rest_v1/page/html/{title}'
    req = urllib.request.Request(url, headers={'Accept': 'text/html', 'User-Agent': 'TaxonomyRebuild/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode('utf-8')
    except Exception:
        return None


def load_page_html(title):
    """Return the page's HTML, using the on-disk cache if present, else fetching
    (and caching) from Wikipedia. Returns None if fetching fails."""
    path = _cache_path(title)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    html = _fetch_wiki_page(title)
    if not html:
        time.sleep(1)
        html = _fetch_wiki_rest(title)
    if html:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        time.sleep(1)
        return html
    return None


if __name__ == '__main__':
    missing = [t for t in WIKI_OUTLINE_PAGES if load_page_html(t) is None]
    print(f'{len(WIKI_OUTLINE_PAGES) - len(missing)}/{len(WIKI_OUTLINE_PAGES)} pages available')
    if missing:
        print('Missing:', missing)
```

- [ ] **Step 4: Run it to confirm caching works and see how many of the previously-missing pages we can now recover**

```bash
python scripts/build_taxonomy.py
```

Expected: `68/72 pages available`, with `Missing: ['Outline_of_cognitive_science',
'Outline_of_database_concepts', 'Outline_of_physical_exercise',
'Outline_of_programming_languages']`. These four were never cached by the earlier
abandoned pipeline attempt; this step retries fetching them live, but they no longer
exist on Wikipedia (`{"code": "missingtitle", "info": "The page you specified
doesn't exist."}`) — confirmed during planning, not a transient failure. `main()` in
Task 4 must skip missing pages gracefully rather than crash (it already does, via the
`html_text is None` check).

- [ ] **Step 5: Commit**

```bash
git add .gitignore scripts/build_taxonomy.py
git commit -m "Add taxonomy pipeline scaffold with cached Wikipedia page fetcher"
```

---

### Task 2: HTML → tree parser

**Files:**
- Modify: `scripts/build_taxonomy.py` (add parsing functions)
- Test: `scripts/test_build_taxonomy.py`

**Interfaces:**
- Consumes: nothing from Task 1 directly (pure function of an HTML string).
- Produces: `normalize_name(name: str) -> str`, `parse_wiki_html_to_tree(html_text:
  str, source_page: str) -> list[dict]`. Each returned node is
  `{'name': str, 'sources': list[tuple[str, str]], 'children': list[dict]}` (a
  heading-derived node additionally carries a transient `'level': int` key, stripped
  later during cleanup).

- [ ] **Step 1: Write the failing test**

```python
# scripts/test_build_taxonomy.py
import unittest
from build_taxonomy import normalize_name, parse_wiki_html_to_tree


class TestNormalizeName(unittest.TestCase):
    def test_lowercases_and_trims(self):
        self.assertEqual(normalize_name('  Anthropology  '), 'anthropology')

    def test_strips_outline_annotation(self):
        self.assertEqual(normalize_name('Anthropology (outline)'), 'anthropology')

    def test_strips_trailing_punctuation(self):
        self.assertEqual(normalize_name('Anthropology.'), 'anthropology')

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_name('Social   science'), 'social science')


class TestParseWikiHtmlToTree(unittest.TestCase):
    SAMPLE_HTML = '''
    <div class="mw-parser-output">
      <div class="mw-heading mw-heading2"><h2 id="Branches">Branches</h2><span class="mw-editsection">[<a href="#">edit</a>]</span></div>
      <ul>
        <li><a href="/wiki/Foo">Foo</a>
          <ul><li><a href="/wiki/Bar">Bar</a></li></ul>
        </li>
        <li><a href="/wiki/Baz">Baz</a></li>
      </ul>
      <div class="mw-heading mw-heading2"><h2 id="See_also">See also</h2><span class="mw-editsection">[<a href="#">edit</a>]</span></div>
      <ul><li><a href="/wiki/Ignored">Ignored</a></li></ul>
    </div>
    '''

    def test_parses_heading_and_nested_list(self):
        tree = parse_wiki_html_to_tree(self.SAMPLE_HTML, 'Outline_of_test')
        self.assertEqual(len(tree), 1)
        branches = tree[0]
        self.assertEqual(branches['name'], 'Branches')
        self.assertEqual(len(branches['children']), 2)
        foo, baz = branches['children']
        self.assertEqual(foo['name'], 'Foo')
        self.assertEqual(foo['sources'], [('wikipedia', 'https://en.wikipedia.org/wiki/Foo')])
        self.assertEqual(len(foo['children']), 1)
        self.assertEqual(foo['children'][0]['name'], 'Bar')
        self.assertEqual(baz['name'], 'Baz')

    def test_skips_see_also_section(self):
        tree = parse_wiki_html_to_tree(self.SAMPLE_HTML, 'Outline_of_test')
        names = [n['name'] for n in tree]
        self.assertNotIn('See also', names)
        self.assertNotIn('Ignored', str(tree))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd scripts && python -m unittest test_build_taxonomy -v
```

Expected: `ImportError: cannot import name 'normalize_name'` (function doesn't exist
yet).

- [ ] **Step 3: Add `normalize_name` and `parse_wiki_html_to_tree` to `scripts/build_taxonomy.py`**

Add near the top (after the imports, before `_cache_path`):

```python
def normalize_name(name):
    """Normalize a discipline name for deduplication comparisons."""
    name = name.lower().strip()
    name = re.sub(r'\s*\(outline\)\s*', '', name)
    name = name.rstrip('.,;:')
    name = ' '.join(name.split())
    return name
```

Add after `load_page_html`:

```python
SKIP_SECTIONS = {
    'See also', 'Notes', 'Further reading', 'External links',
    'References', 'Bibliography', 'Sources', 'Citations',
    'Works cited', 'Footnotes',
}

SKIP_DIV_CLASSES = [
    'hatnote', 'navbox', 'mw-heading', 'noprint', 'reflist',
    'navbox-styles', 'shortdescription', 'mw-references-wrap',
    'gallery', 'thumb', 'mw-empty-elt', 'sidebar', 'quotebox',
    'ambox', 'infobox', 'mw-cite-backlink', 'reference',
]


def parse_wiki_html_to_tree(html_text, source_page):
    """Parse a Wikipedia outline page's HTML into a hierarchical tree.

    Each node: {'name': str, 'sources': [(source, url), ...], 'children': [...]}.
    Heading nodes additionally carry a transient 'level' key.
    """
    from bs4 import BeautifulSoup, NavigableString, Tag

    soup = BeautifulSoup(html_text, 'html.parser')
    content = soup.find('div', class_='mw-parser-output')
    if not content:
        return []

    def get_heading_info(elem):
        if elem.name == 'div' and 'mw-heading' in (elem.get('class') or []):
            for h in elem.find_all(['h2', 'h3', 'h4', 'h5', 'h6']):
                text = h.get_text(strip=True).replace('[edit]', '').strip()
                return (int(h.name[1]), text)
        if elem.name in ('h2', 'h3', 'h4', 'h5', 'h6'):
            text = elem.get_text(strip=True).replace('[edit]', '').strip()
            return (int(elem.name[1]), text)
        return None

    def parse_list_item(li):
        node = {'name': '', 'sources': [], 'children': []}
        parts = []
        first_link = True
        for child in li.children:
            if isinstance(child, Tag):
                if child.name == 'ul':
                    for sub_li in child.find_all('li', recursive=False):
                        node['children'].append(parse_list_item(sub_li))
                elif child.name == 'a':
                    href = child.get('href', '')
                    text = child.get_text(strip=True)
                    parts.append(text)
                    if first_link and 'outline' not in text.lower():
                        if href.startswith('/wiki/'):
                            node['sources'].append(('wikipedia', 'https://en.wikipedia.org' + href))
                            first_link = False
                        elif href.startswith('http'):
                            node['sources'].append(('wikipedia', href))
                            first_link = False
                elif child.name == 'sup':
                    continue
                else:
                    text = child.get_text(strip=True)
                    if text:
                        parts.append(text)
            elif isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    parts.append(text)

        node['name'] = ' '.join(' '.join(parts).split())
        if not node['sources']:
            node['sources'].append(('wikipedia', f'https://en.wikipedia.org/wiki/{source_page}'))
        return node

    def is_content_div(elem):
        if elem.name != 'div':
            return False
        cls = elem.get('class', [])
        return not any(sc in cls for sc in SKIP_DIV_CLASSES)

    def extract_all_lists(elem):
        items = []
        top_level_uls = []
        for ul in elem.find_all('ul'):
            parent = ul.parent
            is_nested = False
            while parent and parent != elem:
                if parent.name == 'li':
                    is_nested = True
                    break
                parent = parent.parent
            if not is_nested:
                top_level_uls.append(ul)
        for ul in top_level_uls:
            for li in ul.find_all('li', recursive=False):
                items.append(parse_list_item(li))
        return items

    tree = []
    section_stack = []

    for child in content.children:
        if not isinstance(child, Tag):
            continue

        heading_info = get_heading_info(child)
        if heading_info:
            level, text = heading_info
            if text in SKIP_SECTIONS:
                section_stack = []
                continue

            node = {
                'name': text,
                'sources': [('wikipedia', f'https://en.wikipedia.org/wiki/{source_page}#{text.replace(" ", "_")}')],
                'children': [],
                'level': level,
            }
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()
            if section_stack:
                section_stack[-1][2]['children'].append(node)
            else:
                tree.append(node)
            section_stack.append((level, text, node))

        elif section_stack:
            items = []
            if child.name == 'div' and 'div-col' in (child.get('class') or []):
                items = extract_all_lists(child)
            elif child.name == 'ul':
                for li in child.find_all('li', recursive=False):
                    items.append(parse_list_item(li))
            elif is_content_div(child):
                items = extract_all_lists(child)
            section_stack[-1][2]['children'].extend(items)

    return tree
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts && python -m unittest test_build_taxonomy -v
```

Expected: `OK` with 5 tests passed (4 `TestNormalizeName` + ... actually 4 normalize
+ 2 parse = 6 tests run, all `ok`).

- [ ] **Step 5: Commit**

```bash
cd .. && git add scripts/build_taxonomy.py scripts/test_build_taxonomy.py
git commit -m "Add Wikipedia outline HTML parser with tests"
```

---

### Task 3: Anchor-based merge + global dedup

**Files:**
- Modify: `scripts/build_taxonomy.py` (add merge/dedup functions)
- Test: `scripts/test_build_taxonomy.py` (append tests)

**Interfaces:**
- Consumes: `normalize_name` (Task 2).
- Produces: `merge_nodes(node_a: dict, node_b: dict) -> dict`,
  `find_node_by_name(nodes: list[dict], target_norm: str) -> dict | None`,
  `dedup_forest(nodes: list[dict]) -> list[dict]`,
  `topic_candidates(page_title: str) -> list[str]`,
  `PAGE_DOMAIN_FALLBACK: dict[str, str]`,
  `merge_page_into_skeleton(skeleton: list[dict], page_title: str, page_tree:
  list[dict]) -> str` (returns the name of the node it merged into, for logging).

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_build_taxonomy.py`:

```python
from build_taxonomy import (
    merge_nodes, find_node_by_name, dedup_forest, topic_candidates,
    merge_page_into_skeleton, PAGE_DOMAIN_FALLBACK, WIKI_OUTLINE_PAGES,
)


def make_node(name, children=None, url=None):
    return {
        'name': name,
        'sources': [('wikipedia', url or f'https://en.wikipedia.org/wiki/{name}')],
        'children': children or [],
    }


class TestMergeNodes(unittest.TestCase):
    def test_merges_children_by_normalized_name_recursively(self):
        a = make_node('Anthropology', [make_node('Archaeology')])
        b = make_node('Anthropology', [make_node('archaeology.'), make_node('Ethnography')])
        merged = merge_nodes(a, b)
        names = sorted(c['name'] for c in merged['children'])
        self.assertEqual(names, ['Archaeology', 'Ethnography'])

    def test_merges_sources_without_duplicating_urls(self):
        a = make_node('Physics', url='https://en.wikipedia.org/wiki/Physics')
        b = make_node('Physics', url='https://en.wikipedia.org/wiki/Physics')
        merged = merge_nodes(a, b)
        self.assertEqual(len(merged['sources']), 1)


class TestFindNodeByName(unittest.TestCase):
    def test_finds_nested_node(self):
        tree = [make_node('Social science', [make_node('Anthropology', [make_node('Archaeology')])])]
        found = find_node_by_name(tree, 'archaeology')
        self.assertIsNotNone(found)
        self.assertEqual(found['name'], 'Archaeology')

    def test_returns_none_when_absent(self):
        tree = [make_node('Social science')]
        self.assertIsNone(find_node_by_name(tree, 'nonexistent'))


class TestDedupForest(unittest.TestCase):
    def test_merges_duplicate_top_level_siblings(self):
        tree = [
            make_node('Anthropology', [make_node('Archaeology')]),
            make_node('Business'),
            make_node('anthropology.', [make_node('Ethnography')]),
        ]
        deduped = dedup_forest(tree)
        names = [n['name'] for n in deduped]
        self.assertEqual(len(names), 2)
        anthro = next(n for n in deduped if normalize_name(n['name']) == 'anthropology')
        child_names = sorted(c['name'] for c in anthro['children'])
        self.assertEqual(child_names, ['Archaeology', 'Ethnography'])

    def test_recurses_into_children(self):
        tree = [make_node('Social science', [
            make_node('Anthropology'),
            make_node('anthropology'),
        ])]
        deduped = dedup_forest(tree)
        self.assertEqual(len(deduped[0]['children']), 1)


class TestTopicCandidates(unittest.TestCase):
    def test_strips_outline_of_prefix(self):
        self.assertIn('artificial intelligence', topic_candidates('Outline_of_artificial_intelligence'))

    def test_adds_the_stripped_variant(self):
        candidates = topic_candidates('Outline_of_the_arts')
        self.assertIn('the arts', candidates)
        self.assertIn('arts', candidates)


class TestMergePageIntoSkeleton(unittest.TestCase):
    def test_merges_into_matching_anchor_by_name(self):
        skeleton = [make_node('Social science', [make_node('Anthropology')])]
        page_tree = [make_node('Branches of anthropology', [make_node('Cultural anthropology')])]
        anchor_name = merge_page_into_skeleton(skeleton, 'Outline_of_anthropology', page_tree)
        self.assertEqual(anchor_name, 'Anthropology')
        anthro = skeleton[0]['children'][0]
        self.assertEqual(anthro['children'][0]['name'], 'Branches of anthropology')

    def test_falls_back_to_domain_when_no_anchor_found(self):
        skeleton = [make_node('Applied science', [])]
        page_tree = [make_node('Types of accounting')]
        anchor_name = merge_page_into_skeleton(skeleton, 'Outline_of_accounting', page_tree)
        self.assertEqual(anchor_name, 'Applied science > Accounting (fallback)')
        accounting_node = skeleton[0]['children'][0]
        self.assertEqual(accounting_node['name'], 'Accounting')
        self.assertEqual(accounting_node['children'][0]['name'], 'Types of accounting')

    def test_fallback_wraps_under_reused_topic_node(self):
        skeleton = [make_node('Humanities', [])]
        merge_page_into_skeleton(skeleton, 'Outline_of_music', [make_node('History of music')])
        merge_page_into_skeleton(skeleton, 'Outline_of_music', [make_node('Music theory')])
        # Both calls must land under the same single "Music" node, not two
        # separate top-level fragments directly on Humanities.
        self.assertEqual(len(skeleton[0]['children']), 1)
        music_node = skeleton[0]['children'][0]
        self.assertEqual(music_node['name'], 'Music')
        self.assertEqual(
            sorted(c['name'] for c in music_node['children']),
            ['History of music', 'Music theory'],
        )

    def test_every_non_skeleton_page_has_a_fallback_domain(self):
        for title in WIKI_OUTLINE_PAGES:
            if title == 'Outline_of_academic_disciplines':
                continue
            self.assertIn(title, PAGE_DOMAIN_FALLBACK, f'{title} missing from PAGE_DOMAIN_FALLBACK')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts && python -m unittest test_build_taxonomy -v
```

Expected: `ImportError: cannot import name 'merge_nodes'`.

- [ ] **Step 3: Add merge/dedup functions and the domain fallback table to `scripts/build_taxonomy.py`**

Add after `parse_wiki_html_to_tree`:

```python
def merge_nodes(node_a, node_b):
    """Merge node_b into node_a in place (sources + children, recursive by name).
    Returns node_a."""
    existing_urls = {s[1] for s in node_a.get('sources', [])}
    for source, url in node_b.get('sources', []):
        if url not in existing_urls:
            node_a.setdefault('sources', []).append((source, url))
            existing_urls.add(url)

    children_by_name = {normalize_name(c['name']): c for c in node_a.get('children', [])}
    for child_b in node_b.get('children', []):
        norm = normalize_name(child_b['name'])
        if norm in children_by_name:
            merge_nodes(children_by_name[norm], child_b)
        else:
            node_a.setdefault('children', []).append(child_b)
            children_by_name[norm] = child_b
    return node_a


def find_node_by_name(nodes, target_norm):
    """DFS a list of nodes for one whose normalized name matches target_norm."""
    for node in nodes:
        if normalize_name(node['name']) == target_norm:
            return node
        found = find_node_by_name(node.get('children', []), target_norm)
        if found:
            return found
    return None


def dedup_siblings(node):
    """Recursively merge node's direct children that share a normalized name."""
    children = node.get('children', [])
    merged, by_name = [], {}
    for child in children:
        norm = normalize_name(child['name'])
        if norm in by_name:
            merge_nodes(by_name[norm], child)
        else:
            by_name[norm] = child
            merged.append(child)
    node['children'] = merged
    for child in merged:
        dedup_siblings(child)


def dedup_forest(nodes):
    """Deduplicate a bare list of top-level nodes (no shared parent) and recurse."""
    merged, by_name = [], {}
    for node in nodes:
        norm = normalize_name(node['name'])
        if norm in by_name:
            merge_nodes(by_name[norm], node)
        else:
            by_name[norm] = node
            merged.append(node)
    for node in merged:
        dedup_siblings(node)
    return merged


def topic_candidates(page_title):
    """Candidate discipline names to search for, derived from an outline page title."""
    base = page_title
    if base.startswith('Outline_of_'):
        base = base[len('Outline_of_'):]
    base = base.replace('_', ' ').lower()
    candidates = [base]
    if base.startswith('the '):
        candidates.append(base[4:])
    return candidates


# Fallback parent domain for every non-skeleton page, used only when
# topic_candidates() finds no matching node anywhere in the skeleton.
PAGE_DOMAIN_FALLBACK = {
    'Outline_of_accounting': 'Applied science',
    'Outline_of_agriculture': 'Applied science',
    'Outline_of_anthropology': 'Social science',
    'Outline_of_applied_science': 'Applied science',
    'Outline_of_archaeology': 'Social science',
    'Outline_of_architecture': 'Applied science',
    'Outline_of_artificial_intelligence': 'Formal science',
    'Outline_of_astronomy': 'Natural science',
    'Outline_of_biology': 'Natural science',
    'Outline_of_business': 'Applied science',
    'Outline_of_chemistry': 'Natural science',
    'Outline_of_cognitive_science': 'Social science',
    'Outline_of_communication': 'Social science',
    'Outline_of_computer_science': 'Formal science',
    'Outline_of_cooking': 'Applied science',
    'Outline_of_cryptography': 'Formal science',
    'Outline_of_cuisines': 'Applied science',
    'Outline_of_culture': 'Humanities',
    'Outline_of_dance': 'Humanities',
    'Outline_of_database_concepts': 'Formal science',
    'Outline_of_earth_science': 'Natural science',
    'Outline_of_economics': 'Social science',
    'Outline_of_education': 'Applied science',
    'Outline_of_energy': 'Applied science',
    'Outline_of_energy_development': 'Applied science',
    'Outline_of_energy_storage': 'Applied science',
    'Outline_of_engineering': 'Applied science',
    'Outline_of_film': 'Humanities',
    'Outline_of_finance': 'Applied science',
    'Outline_of_food_preparation': 'Applied science',
    'Outline_of_formal_science': 'Formal science',
    'Outline_of_geography': 'Social science',
    'Outline_of_health': 'Applied science',
    'Outline_of_history': 'Humanities',
    'Outline_of_journalism': 'Applied science',
    'Outline_of_law': 'Humanities',
    'Outline_of_linguistics': 'Social science',
    'Outline_of_literature': 'Humanities',
    'Outline_of_logic': 'Formal science',
    'Outline_of_machine_learning': 'Formal science',
    'Outline_of_management': 'Applied science',
    'Outline_of_marketing': 'Applied science',
    'Outline_of_mathematics': 'Formal science',
    'Outline_of_medicine': 'Applied science',
    'Outline_of_military_science_and_technology': 'Applied science',
    'Outline_of_music': 'Humanities',
    'Outline_of_natural_science': 'Natural science',
    'Outline_of_neuroscience': 'Natural science',
    'Outline_of_nutrition': 'Applied science',
    'Outline_of_performing_arts': 'Humanities',
    'Outline_of_philosophy': 'Humanities',
    'Outline_of_physical_exercise': 'Applied science',
    'Outline_of_physics': 'Natural science',
    'Outline_of_political_science': 'Social science',
    'Outline_of_programming_languages': 'Formal science',
    'Outline_of_psychology': 'Social science',
    'Outline_of_religion': 'Humanities',
    'Outline_of_robotics': 'Applied science',
    'Outline_of_social_science': 'Social science',
    'Outline_of_sociology': 'Social science',
    'Outline_of_software_engineering': 'Formal science',
    'Outline_of_sports': 'Applied science',
    'Outline_of_statistics': 'Formal science',
    'Outline_of_television_broadcasting': 'Applied science',
    'Outline_of_the_Internet': 'Formal science',
    'Outline_of_the_arts': 'Humanities',
    'Outline_of_the_humanities': 'Humanities',
    'Outline_of_the_visual_arts': 'Humanities',
    'Outline_of_theatre': 'Humanities',
    'Outline_of_transport': 'Applied science',
    'Outline_of_video_games': 'Applied science',
}


def _merge_children_list_by_name(target_node, new_children):
    existing_by_name = {normalize_name(c['name']): c for c in target_node.get('children', [])}
    for child in new_children:
        norm = normalize_name(child['name'])
        if norm in existing_by_name:
            merge_nodes(existing_by_name[norm], child)
        else:
            target_node.setdefault('children', []).append(child)
            existing_by_name[norm] = child


def merge_page_into_skeleton(skeleton, page_title, page_tree):
    """Merge a parsed outline page's tree into the skeleton at the correct anchor.
    Returns the name of the node it merged into (with ' (fallback)' suffix if the
    domain fallback was used), for logging."""
    for candidate in topic_candidates(page_title):
        anchor = find_node_by_name(skeleton, normalize_name(candidate))
        if anchor:
            _merge_children_list_by_name(anchor, page_tree)
            return anchor['name']

    domain_name = PAGE_DOMAIN_FALLBACK.get(page_title)
    if not domain_name:
        raise ValueError(f'No domain fallback mapping for {page_title}')
    domain_node = find_node_by_name(skeleton, normalize_name(domain_name))
    if domain_node is None:
        raise ValueError(f'Domain node {domain_name!r} not found in skeleton for {page_title}')

    # Don't dump the page's raw top-level sections directly onto the domain —
    # that mixes unrelated pages' sections as siblings and, worse, lets a
    # page's own section titles collide with real domain names. Wrap them
    # under a topic node named after the page instead, same shape as a
    # properly-anchored merge would produce.
    topic_label = topic_candidates(page_title)[-1].title()
    topic_anchor = find_node_by_name(domain_node.get('children', []), normalize_name(topic_label))
    if topic_anchor is None:
        topic_anchor = {
            'name': topic_label,
            'sources': [('wikipedia', f'https://en.wikipedia.org/wiki/{page_title}')],
            'children': [],
        }
        domain_node.setdefault('children', []).append(topic_anchor)
    _merge_children_list_by_name(topic_anchor, page_tree)
    return f'{domain_name} > {topic_label} (fallback)'
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts && python -m unittest test_build_taxonomy -v
```

Expected: `OK`, all tests pass (the `test_every_non_skeleton_page_has_a_fallback_domain`
test is what confirms the table has all 71 entries — if it fails, the printed
assertion names the missing page title to add).

- [ ] **Step 5: Commit**

```bash
cd .. && git add scripts/build_taxonomy.py scripts/test_build_taxonomy.py
git commit -m "Add anchor-based merge and global dedup for taxonomy pipeline"
```

---

### Task 4: Output generators + full pipeline wiring

**Files:**
- Modify: `scripts/build_taxonomy.py` (add cleanup/sort, output generators, `main()`)
- Test: `scripts/test_build_taxonomy.py` (append tests)

**Interfaces:**
- Consumes: `dedup_forest`, `merge_page_into_skeleton`, `parse_wiki_html_to_tree`,
  `load_page_html`, `WIKI_OUTLINE_PAGES` (all from Tasks 1-3).
- Produces: `cleanup_node(node: dict) -> None` (strips transient keys in place),
  `sort_tree(node: dict) -> None` (sorts children alphabetically in place),
  `to_compact_tree(node: dict) -> dict`, `flatten_for_search(node, path, depth, out)
  -> None`, `_resolved_page_title(html_text: str) -> str | None` (extracts the page
  title Wikipedia actually rendered, to detect pages whose cached/fetched content is
  really a different page — see Step 3), `build_taxonomy() -> list[dict]` (the full
  pipeline), and a `main()` that writes all four output files.

**Why the `_resolved_page_title` guard exists:** while smoke-testing this pipeline
against the real cached pages during planning, `Outline_of_the_arts` turned out to
be a redirect whose actual rendered content is `Outline_of_academic_disciplines` in
full — merging it (even through the Task 3 fallback-wrapping fix) nested an entire
second copy of the whole tree under a synthetic "Arts" node. The guard detects when
a page's real content belongs to *another page already in `WIKI_OUTLINE_PAGES`* and
skips merging it, since that content is already covered by processing the other page
directly.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_build_taxonomy.py`:

```python
from build_taxonomy import cleanup_node, sort_tree, to_compact_tree, flatten_for_search


class TestCleanupAndSort(unittest.TestCase):
    def test_cleanup_strips_level_key(self):
        node = {'name': 'X', 'sources': [], 'children': [], 'level': 2}
        cleanup_node(node)
        self.assertNotIn('level', node)

    def test_sort_orders_children_case_insensitively(self):
        node = make_node('Root', [make_node('banana'), make_node('Apple')])
        sort_tree(node)
        self.assertEqual([c['name'] for c in node['children']], ['Apple', 'banana'])


class TestCompactOutputs(unittest.TestCase):
    def test_to_compact_tree_picks_wikipedia_url(self):
        node = make_node('Physics', [make_node('Optics')], url='https://en.wikipedia.org/wiki/Physics')
        compact = to_compact_tree(node)
        self.assertEqual(compact, {
            'n': 'Physics',
            'u': 'https://en.wikipedia.org/wiki/Physics',
            'c': [{'n': 'Optics', 'u': 'https://en.wikipedia.org/wiki/Optics', 'c': []}],
        })

    def test_flatten_for_search_builds_paths_and_depths(self):
        node = make_node('Humanities', [make_node('History')])
        out = []
        flatten_for_search(node, [], 0, out)
        self.assertEqual(out, [
            {'n': 'Humanities', 'p': 'Humanities', 'u': 'https://en.wikipedia.org/wiki/Humanities', 'd': 0},
            {'n': 'History', 'p': 'Humanities > History', 'u': 'https://en.wikipedia.org/wiki/History', 'd': 1},
        ])


class TestResolvedPageTitle(unittest.TestCase):
    def test_extracts_title_from_edit_section_link(self):
        html = ('<div class="mw-heading mw-heading2"><h2 id="X">X</h2>'
                '<span class="mw-editsection"><a href="/w/index.php?'
                'title=Outline_of_academic_disciplines&amp;action=edit&amp;section=1">edit</a>'
                '</span></div>')
        self.assertEqual(_resolved_page_title(html), 'Outline_of_academic_disciplines')

    def test_returns_none_when_no_edit_link_present(self):
        self.assertIsNone(_resolved_page_title('<div>no edit links here</div>'))
```

Also add `_resolved_page_title` to the import line at the top of
`scripts/test_build_taxonomy.py`:

```python
from build_taxonomy import (
    normalize_name, parse_wiki_html_to_tree,
    merge_nodes, find_node_by_name, dedup_forest, topic_candidates,
    merge_page_into_skeleton, PAGE_DOMAIN_FALLBACK, WIKI_OUTLINE_PAGES,
    cleanup_node, sort_tree, to_compact_tree, flatten_for_search,
    _resolved_page_title,
)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts && python -m unittest test_build_taxonomy -v
```

Expected: `ImportError: cannot import name 'cleanup_node'`.

- [ ] **Step 3: Add the remaining functions to `scripts/build_taxonomy.py`**

```python
def cleanup_node(node):
    """Strip transient parsing keys (in place, recursive)."""
    node.pop('level', None)
    for c in node.get('children', []):
        cleanup_node(c)


def sort_tree(node):
    """Sort children alphabetically, case-insensitive (in place, recursive)."""
    for c in node.get('children', []):
        sort_tree(c)
    node['children'].sort(key=lambda x: x['name'].lower())


def count_nodes(node):
    return 1 + sum(count_nodes(c) for c in node.get('children', []))


def _primary_url(node):
    for src, url in node.get('sources', []):
        if src == 'wikipedia':
            return url
    sources = node.get('sources', [])
    return sources[0][1] if sources else ''


def to_compact_tree(node):
    return {
        'n': node['name'],
        'u': _primary_url(node),
        'c': [to_compact_tree(c) for c in node.get('children', [])],
    }


def flatten_for_search(node, path, depth, out):
    full_path = path + [node['name']]
    out.append({'n': node['name'], 'p': ' > '.join(full_path), 'u': _primary_url(node), 'd': depth})
    for c in node.get('children', []):
        flatten_for_search(c, full_path, depth + 1, out)


def _resolved_page_title(html_text):
    """Best-effort extraction of the page title Wikipedia actually rendered,
    via a section-edit link's title= query param. Returns None if not found."""
    match = re.search(r'title=([A-Za-z0-9_]+)&amp;action=edit', html_text)
    return match.group(1) if match else None


def build_taxonomy():
    """Run the full pipeline: parse all pages, merge into the skeleton, dedup.
    Returns the final list of top-level domain nodes."""
    skeleton_html = load_page_html('Outline_of_academic_disciplines')
    if skeleton_html is None:
        raise RuntimeError('Could not load the Outline_of_academic_disciplines skeleton page')
    skeleton = parse_wiki_html_to_tree(skeleton_html, 'Outline_of_academic_disciplines')

    for title in WIKI_OUTLINE_PAGES:
        if title == 'Outline_of_academic_disciplines':
            continue
        html_text = load_page_html(title)
        if html_text is None:
            print(f'  SKIP (fetch failed): {title}')
            continue

        resolved = _resolved_page_title(html_text)
        if resolved and resolved != title and resolved in WIKI_OUTLINE_PAGES:
            # This page's real content is a duplicate of another page we
            # already fetch and merge independently.
            print(f'  SKIP (duplicate content, resolves to {resolved}): {title}')
            continue

        page_tree = parse_wiki_html_to_tree(html_text, title)
        anchor_name = merge_page_into_skeleton(skeleton, title, page_tree)
        print(f'  merged {title} -> {anchor_name}')

    skeleton = dedup_forest(skeleton)
    for node in skeleton:
        cleanup_node(node)
        sort_tree(node)
    return skeleton


def main():
    print('Building taxonomy from Wikipedia Outline pages...')
    tree = build_taxonomy()
    total = sum(count_nodes(n) for n in tree)
    print(f'\nFinal tree: {total} nodes')
    for n in tree:
        print(f'  {n["name"]}: {count_nodes(n)}')

    with open(os.path.join(REPO_DIR, 'taxonomy.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)

    compact_tree = [to_compact_tree(n) for n in tree]
    with open(os.path.join(REPO_DIR, 'tree-data.js'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('const RAW_TREE = ' + json.dumps(compact_tree, ensure_ascii=False, separators=(',', ':')) + ';\n')

    flat = []
    for n in tree:
        flatten_for_search(n, [], 0, flat)
    with open(os.path.join(REPO_DIR, 'flat-data.js'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('const RAW_FLAT = ' + json.dumps(flat, ensure_ascii=False, separators=(',', ':')) + ';\n')

    flat_full = [{'name': x['n'], 'path': x['p'], 'url': x['u'], 'depth': x['d']} for x in flat]
    with open(os.path.join(REPO_DIR, 'taxonomy_flat.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(flat_full, f, ensure_ascii=False, indent=2)

    print(f'\nWrote taxonomy.json, tree-data.js, flat-data.js, taxonomy_flat.json ({total} nodes, {len(flat)} flat entries)')


if __name__ == '__main__':
    main()
```

Note this **replaces** the old `if __name__ == '__main__':` block from Task 1 Step 3
— there should be only one at the bottom of the file after this step.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts && python -m unittest test_build_taxonomy -v
```

Expected: `OK`, all tests pass.

- [ ] **Step 5: Commit**

```bash
cd .. && git add scripts/build_taxonomy.py scripts/test_build_taxonomy.py
git commit -m "Wire up full taxonomy pipeline with compact JS/JSON output generators"
```

---

### Task 5: Validator script

**Files:**
- Create: `scripts/verify_taxonomy.py`

**Interfaces:**
- Consumes: `../taxonomy.json` (the file `main()` in Task 4 writes).
- Produces: a CLI script; exits 1 if any duplicate sibling names are found, 0
  otherwise. Prints anomaly warnings (non-fatal) for branches whose size is more
  than 3x their sibling median.

- [ ] **Step 1: Write `scripts/verify_taxonomy.py`**

```python
#!/usr/bin/env python3
"""Validate the rebuilt taxonomy.json: hard-fail on duplicate sibling names,
warn on branches whose size looks anomalous relative to their siblings."""
import json
import os
import re
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normalize_name(name):
    name = name.lower().strip()
    name = re.sub(r'\s*\(outline\)\s*', '', name)
    name = name.rstrip('.,;:')
    return ' '.join(name.split())


def count_nodes(node):
    return 1 + sum(count_nodes(c) for c in node.get('children', []))


def median(values):
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return (s[mid - 1] + s[mid]) / 2 if n % 2 == 0 else s[mid]


def check_duplicates(node, path, errors):
    seen = {}
    for child in node.get('children', []):
        norm = normalize_name(child['name'])
        if norm in seen:
            errors.append(f"Duplicate sibling '{child['name']}' under {' > '.join(path) or 'root'}")
        else:
            seen[norm] = child
        check_duplicates(child, path + [child['name']], errors)


def report_anomalies(node, path, warnings):
    children = node.get('children', [])
    if len(children) >= 4:
        counts = [count_nodes(c) for c in children]
        med = median(counts)
        if med > 0:
            for c, cnt in zip(children, counts):
                if cnt > med * 3:
                    warnings.append(
                        f"{c['name']} under {' > '.join(path) or 'root'}: "
                        f"{cnt} nodes vs sibling median {med:.0f}"
                    )
    for child in children:
        report_anomalies(child, path + [child['name']], warnings)


def main():
    with open(os.path.join(REPO_DIR, 'taxonomy.json'), encoding='utf-8') as f:
        tree = json.load(f)

    total = sum(count_nodes(n) for n in tree)
    print(f'Total nodes: {total}')
    for n in tree:
        print(f'  {n["name"]}: {count_nodes(n)}')

    errors = []
    for node in tree:
        check_duplicates(node, [node['name']], errors)
    # also check duplicates among the top-level domain nodes themselves
    check_duplicates({'children': tree}, [], errors)

    warnings = []
    for node in tree:
        report_anomalies(node, [], warnings)

    if errors:
        print(f'\nDUPLICATE SIBLINGS ({len(errors)}):')
        for e in errors[:50]:
            print(' -', e)
    else:
        print('\nNo duplicate siblings found.')

    if warnings:
        print(f'\nSIZE ANOMALIES for manual review ({len(warnings)}):')
        for w in warnings[:50]:
            print(' -', w)

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Confirm it fails loudly against the still-broken repo `taxonomy.json`**
  (this file hasn't been regenerated yet — Task 6 does that — so this is a smoke
  test of the validator itself against known-bad data)

```bash
python scripts/verify_taxonomy.py; echo "exit code: $?"
```

Expected: exit code `1`, with the "Anthropology" / "Business" / etc. duplicates and
the "Public administration" anomaly listed — confirming the validator actually
detects the known bugs described in the spec.

- [ ] **Step 3: Commit**

```bash
git add scripts/verify_taxonomy.py
git commit -m "Add taxonomy validator: dedup check plus size-anomaly report"
```

---

### Task 6: Run the full rebuild, validate, update README, verify in the app

**Files:**
- Modify: `taxonomy.json`, `tree-data.js`, `flat-data.js`, `taxonomy_flat.json`
  (regenerated)
- Modify: `README.md`

**Interfaces:**
- Consumes: `scripts/build_taxonomy.py main()`, `scripts/verify_taxonomy.py main()`.
- Produces: the shipped data files for `index.html`.

- [ ] **Step 1: Audit the cache for pages whose content doesn't match their filename**

Some of the pages cached in Task 1 Step 2 turn out to be corrupted or stale — either
a genuine Wikipedia redirect (harmless) or a fetch-time glitch that cached the wrong
content entirely (harmful). Run this check before the real build:

```bash
python3 -c "
import os, re
cache_dir = 'scripts/.cache_wiki'
for fname in sorted(os.listdir(cache_dir)):
    if not (fname.startswith('wiki_Outline_of_') and fname.endswith('.html')):
        continue
    expected = fname[len('wiki_'):-len('.html')]
    with open(os.path.join(cache_dir, fname), encoding='utf-8') as f:
        html = f.read()
    m = re.search(r'title=([A-Za-z0-9_]+)&amp;action=edit', html)
    if m and m.group(1) != expected:
        print(f'{expected}  ->  actually contains: {m.group(1)}')
"
```

Expected output includes a line `Outline_of_education  ->  actually contains:
Education_in_the_Sahrawi_Arab_Democratic_Republic` — this is a fetch-time glitch (not
a real Wikipedia redirect) that would inject unrelated content into the "Education"
branch. `build_taxonomy()`'s `_resolved_page_title` guard (Task 4) only skips pages
that duplicate *another page already in `WIKI_OUTLINE_PAGES`*, so it won't catch
this one — clear the bad cache entry and let `load_page_html` re-fetch it fresh:

```bash
rm scripts/.cache_wiki/wiki_Outline_of_education.html
python3 -c "import sys; sys.path.insert(0, 'scripts'); from build_taxonomy import load_page_html; html = load_page_html('Outline_of_education'); print('refetched OK' if html else 'FETCH FAILED')"
```

If it re-resolves correctly this time (check with the same audit one-liner above —
`Outline_of_education` should no longer appear in the mismatch list), proceed. If the
fetch fails or still mismatches, leave a note in the merge log review (Step 2) rather
than blocking — a missing/wrong "Education" branch is a smaller problem than a
crashed pipeline.

The other mismatches you'll see (`Outline_of_cooking` → `Outline_of_food_preparation`,
`Outline_of_earth_science` → `Outline_of_Earth_science`, `Outline_of_energy_storage`
→ `Energy_storage`, `Outline_of_formal_science` → `Formal_science`,
`Outline_of_mathematics` → `Lists_of_mathematics_topics`, `Outline_of_nutrition` →
`Nutrition`, `Outline_of_the_arts` → `Outline_of_academic_disciplines`) are legitimate
Wikipedia redirects to real, on-topic content — no action needed; `_resolved_page_title`
already handles the `Outline_of_the_arts` and `Outline_of_cooking` cases (both resolve
to another tracked page) by skipping them in Step 2 below.

- [ ] **Step 2: Run the full pipeline**

```bash
python scripts/build_taxonomy.py
```

Expected: a `merged <page> -> <anchor>` line for most pages, `SKIP (fetch failed):
<page>` for `Outline_of_cognitive_science`, `Outline_of_database_concepts`,
`Outline_of_physical_exercise`, and `Outline_of_programming_languages` (confirmed
during planning via a direct Wikipedia API call: these four titles no longer exist —
`{"code": "missingtitle", "info": "The page you specified doesn't exist."}` — not a
network issue, so don't spend time troubleshooting connectivity here), `SKIP
(duplicate content, resolves to Outline_of_food_preparation): Outline_of_cooking` and
`SKIP (duplicate content, resolves to Outline_of_academic_disciplines):
Outline_of_the_arts`, a final node count summary per domain, and `Wrote
taxonomy.json, tree-data.js, flat-data.js, taxonomy_flat.json (N nodes, M flat
entries)`. Read through the merge log for any `(fallback)` anchors and confirm the
domain assignment looks reasonable.

- [ ] **Step 3: Run the validator**

```bash
python scripts/verify_taxonomy.py; echo "exit code: $?"
```

Expected: exit code `0`, `No duplicate siblings found.`. If duplicates are still
reported, that's a real bug in Task 3's merge logic (not something to patch around
here) — go back and fix `merge_page_into_skeleton` or `dedup_forest`, re-run Task 3's
tests, then re-run this task from Step 1.

Expect the total node count to land well above the original 6,806 — a from-scratch
run during planning produced ~27,700 nodes with zero duplicate siblings. That jump is
expected and correct: the original tree was losing most of each page's content to
the flat top-level merge bug (see spec), not genuinely covering that much less
material. A much bigger, duplicate-free count is the intended outcome, not a red flag
by itself — the validator's "no duplicate siblings" result is what actually confirms
correctness, not the total matching any particular number.

Review the `SIZE ANOMALIES` warnings (non-fatal) manually: for each one, open the
corresponding Wikipedia outline page and confirm the branch size is plausible given
that page's actual content. If a branch is still implausible, investigate whether a
page merged into the wrong anchor (check the Step 2 merge log for that discipline's
name) and fix the `topic_candidates` / `PAGE_DOMAIN_FALLBACK` logic accordingly.

- [ ] **Step 4: Spot-check against live Wikipedia**

Manually compare the rebuilt tree's top-level structure for at least these domains
against their current Wikipedia pages, since the design doc flagged them as
suspiciously shallow before the rebuild:
- Natural science vs https://en.wikipedia.org/wiki/Outline_of_natural_science
- Formal science vs https://en.wikipedia.org/wiki/Outline_of_formal_science

Confirm both now show branches for the major sub-fields those pages actually list
(e.g. Physics, Chemistry, Astronomy, Earth science under Natural science; Statistics,
Systems science under Formal science) rather than just 2-3 children.

- [ ] **Step 5: Update `README.md` stats**

Read the current total node count and structure from the Step 2 output, then update
the README's stated numbers (currently "Interactive browser for 6,806 academic
disciplines" and "Collapsible tree of 6,806 disciplines... 10 levels deep") to match
the actual rebuilt totals and max depth.

- [ ] **Step 6: Load `index.html` locally and confirm it renders correctly**

```bash
python -m http.server 8000
```

Open `http://localhost:8000/index.html` in a browser. Confirm:
- The tree renders with no console errors.
- The discipline count shown in the header matches the validator's total.
- Search works and returns results.
- Expanding "Anthropology" (or any previously-duplicated branch) under Social
  science shows exactly one branch, not two.
- Clicking a discipline still shows it in the Reading List tab's "Selected" field.

Stop the server (Ctrl+C) when done.

- [ ] **Step 7: Commit the regenerated data and README**

```bash
git add taxonomy.json tree-data.js flat-data.js taxonomy_flat.json README.md
git commit -m "Rebuild taxonomy from Wikipedia outlines with corrected merge/dedup"
```

---

## Self-Review Notes

- **Spec coverage:** every item in the spec's "Approach" section (1-6) maps to a
  task above — parser reuse (Task 2), anchor-based merge (Task 3), global dedup
  (Task 3), Public administration anomaly resolution (Task 6 Step 2-3, since it's
  not producible by this pipeline at all — confirmed absent rather than explicitly
  "removed"), validation (Task 5 + Task 6 Steps 3-4), output format compatibility
  (Task 4).
- **Type consistency:** `merge_page_into_skeleton` returns a `str` (used only for
  logging) in both its test and its use in `build_taxonomy()`. `to_compact_tree` /
  `flatten_for_search` dict shapes match exactly what `index.html`'s
  `expandNode()`/`loadTaxonomy()` already expect (`n`/`u`/`c` and `n`/`p`/`u`/`d`).
- **This plan was smoke-tested against the real repo and real cached Wikipedia data
  during planning**, not just reasoned about — every code block in Tasks 2-4 was
  extracted, run, and its unit tests executed (22 passing), and the full pipeline was
  run end-to-end against the actual 68 cached pages. That run caught two real bugs
  that are now baked into the task steps above rather than left for the implementer
  to discover: (1) the original fallback design dumped a page's raw sections
  directly onto its domain node instead of wrapping them under a topic node, which
  let one page's section titles collide with real domain names — fixed in Task 3's
  `merge_page_into_skeleton`; (2) `Outline_of_the_arts`'s cached HTML is actually a
  full copy of `Outline_of_academic_disciplines`'s content (confirmed via the page's
  own edit-section links), which was nesting an entire duplicate copy of the whole
  tree under a synthetic "Arts" node — fixed via the `_resolved_page_title` guard in
  Task 4. A third, unrelated issue (`Outline_of_education`'s cache containing an
  unrelated country's education article, apparently a fetch-time glitch) is handled
  as a cache-audit step at the start of Task 6 rather than in code, since it's a
  one-off bad cache entry rather than a systematic bug.
- Once this lands and is confirmed working, Phase 2 (reading list generator
  rebuild with IndexedDB caching, wiki scanner fix, new LLM-based expand-node
  feature, OpenRouter model list update) gets its own brainstorming session and
  design doc, since it depends on this corrected tree as its foundation.
