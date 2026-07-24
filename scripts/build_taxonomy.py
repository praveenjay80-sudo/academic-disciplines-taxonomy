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

def normalize_name(name):
    """Normalize a discipline name for deduplication comparisons."""
    name = name.lower().strip()
    name = re.sub(r'\s*\(outline\)\s*', '', name)
    name = name.rstrip('.,;:')
    name = ' '.join(name.split())
    return name


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


# Node names above this length with no clean separator to split at are
# treated as junk (leaked Wikipedia CSS, full bibliographic citations, etc)
# rather than real discipline names, and dropped.
JUNK_NAME_MAX_LEN = 200


def clean_node_name(name):
    """Split Wikipedia definition-list-style 'Term – long description' names
    down to just the term. Returns the cleaned name, or None if the node is
    junk (empty, or too long with no clean split point) and should be dropped."""
    name = ' '.join(name.split())
    for sep in (' – ', ' — '):
        if sep in name:
            name = name.split(sep, 1)[0].strip()
            break
    else:
        if len(name) > 60 and ' - ' in name:
            name = name.split(' - ', 1)[0].strip()
    if not name:
        return None
    if len(name) > JUNK_NAME_MAX_LEN:
        return None
    return name


def clean_tree_names(nodes):
    """Recursively clean/split node names. A node that cleans to junk is
    removed, and its own (already-cleaned) children are spliced into its
    position so real sub-disciplines under a junk entry aren't lost."""
    cleaned = []
    for node in nodes:
        node['children'] = clean_tree_names(node.get('children', []))
        new_name = clean_node_name(node['name'])
        if new_name is None:
            cleaned.extend(node['children'])
        else:
            node['name'] = new_name
            cleaned.append(node)
    return cleaned


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

    skeleton = clean_tree_names(skeleton)
    # Cleaning can turn two previously-distinct names into the same name
    # (e.g. two different long descriptions that both start with "History"),
    # so dedup must run after cleaning, not before.
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
