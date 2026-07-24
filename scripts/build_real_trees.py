#!/usr/bin/env python3
"""Convert real structured taxonomy sources (MSC2020, PhySH, ACM CCS) into
compact JSON trees for the app. No scraping, no merging across sources —
each is already a complete, authoritative classification; this just
reshapes each one's own native format into {n, u, c} nodes."""
import csv
import json
import re
import xml.etree.ElementTree as ET

# ============================================================
# MSC2020 -> Mathematics tree
# ============================================================
def build_msc_tree():
    with open('msc2020.csv', encoding='latin-1') as f:
        rows = list(csv.DictReader(f, delimiter='\t'))

    divisions = {}   # '00' -> node
    groups = {}       # '00A' -> node

    div_re = re.compile(r'^(\d{2})-XX$')
    direct_re = re.compile(r'^(\d{2})-\d{2}$')
    group_re = re.compile(r'^(\d{2}[A-Za-z])xx$')
    topic_re = re.compile(r'^(\d{2}[A-Za-z])\d{2}$')

    # pass 1: divisions
    for r in rows:
        code = r['code'].strip()
        m = div_re.match(code)
        if m:
            divisions[m.group(1)] = {'n': r['text'].strip(), 'u': None, 'c': []}

    # pass 2: groups
    for r in rows:
        code = r['code'].strip()
        m = group_re.match(code)
        if m:
            prefix = m.group(1)
            div_key = prefix[:2]
            node = {'n': r['text'].strip(), 'u': None, 'c': []}
            groups[prefix] = node
            if div_key in divisions:
                divisions[div_key]['c'].append(node)

    # pass 3: topic leaves under groups only.
    # Deliberately skip "direct leaf" entries entirely (the \d{2}-\d{2}
    # codes, e.g. "01-06 Proceedings, conferences, collections... pertaining
    # to X") -- every one of these is a standardized publication-FORMAT
    # classifier (introductory exposition, historical, proceedings,
    # computation, etc.) repeated across every division, not an academic
    # subject. A reading list "about proceedings pertaining to number
    # theory" isn't a real thing; "Number theory" itself already exists as
    # its own node. Also skip administrative topic leaves that aren't real
    # subjects either (reference-works/proceedings meta-entries).
    NON_TOPIC_PREFIXES = ('general reference works', 'conference proceedings and collections of articles')
    for r in rows:
        code = r['code'].strip()
        m = topic_re.match(code)
        if m:
            text = r['text'].strip()
            if text.lower().startswith(NON_TOPIC_PREFIXES):
                continue
            prefix = m.group(1)
            if prefix in groups:
                groups[prefix]['c'].append({'n': text, 'u': None, 'c': []})

    tree = list(divisions.values())
    return tree


# ============================================================
# PhySH -> Physics tree (full tree, all 18 disciplines)
# ============================================================
def build_physh_tree():
    data = json.load(open('physh.json', encoding='utf-8'))
    by_id = {d['@id']: d for d in data}

    def label(d):
        for k in d:
            if k.endswith('prefLabel'):
                return d[k][0]['@value']
        return '(unlabeled)'

    def get_ids(d, suffix):
        for k in d:
            if k.endswith(suffix):
                return [x['@id'] for x in d[k]]
        return []

    # Build children-by-broader map
    children_of = {}
    for d in data:
        broader = get_ids(d, 'broader')
        if broader:
            children_of.setdefault(broader[0], []).append(d['@id'])

    # discipline root ids: things referenced via inDiscipline that are
    # themselves concepts (these act as the 18 top-level buckets)
    discipline_ids = set()
    facet_top_by_discipline = {}  # discipline_id -> list of concept ids with no broader but inDiscipline set
    for d in data:
        disc = get_ids(d, 'inDiscipline')
        if disc:
            discipline_ids.add(disc[0])
            if 'http://www.w3.org/2004/02/skos/core#broader' not in ''.join(d.keys()):
                pass

    # "Professional Topics" facet is audience/career categories (K-12
    # teachers, undergraduate students, faculty, ...) -- not academic
    # subject matter, nothing there is capable of a reading list.
    professional_topics_facet_id = None
    for d in data:
        if label(d) == 'Professional Topics':
            professional_topics_facet_id = d['@id']
            break

    for d in data:
        disc = get_ids(d, 'inDiscipline')
        broader = get_ids(d, 'broader')
        facet = get_ids(d, 'inFacet')
        if facet and facet[0] == professional_topics_facet_id:
            continue
        if disc and not broader:
            facet_top_by_discipline.setdefault(disc[0], []).append(d['@id'])

    visited = set()

    def build_node(cid, depth):
        if cid in visited or cid not in by_id:
            return None
        visited.add(cid)
        d = by_id[cid]
        node = {'n': label(d), 'u': None, 'c': []}
        if depth < 8:  # safety cap against any accidental cycles
            for child_id in children_of.get(cid, []):
                child_node = build_node(child_id, depth + 1)
                if child_node:
                    node['c'].append(child_node)
        return node

    tree = []
    for disc_id in sorted(discipline_ids, key=lambda i: label(by_id.get(i, {})) if i in by_id else i):
        if disc_id not in by_id:
            continue
        visited.add(disc_id)
        disc_node = {'n': label(by_id[disc_id]), 'u': None, 'c': []}
        for top_id in facet_top_by_discipline.get(disc_id, []):
            child_node = build_node(top_id, 1)
            if child_node:
                disc_node['c'].append(child_node)
        tree.append(disc_node)

    return tree


# ============================================================
# ACM CCS -> full Computer Science tree (all top concepts, not just
# the "Theory of computation" branch)
# ============================================================
def build_ccs_tree():
    ns = {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'skos': 'http://www.w3.org/2004/02/skos/core#'}
    tree_xml = ET.parse('acm_ccs.xml')
    root = tree_xml.getroot()
    RDF_ABOUT = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about'
    RDF_RESOURCE = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource'

    concepts = {}
    for c in root.findall('skos:Concept', ns):
        cid = c.get(RDF_ABOUT)
        label_el = c.find('skos:prefLabel', ns)
        label = label_el.text.strip() if label_el is not None and label_el.text else '(unlabeled)'
        narrower = [n.get(RDF_RESOURCE) for n in c.findall('skos:narrower', ns)]
        concepts[cid] = {'label': label, 'narrower': narrower}

    scheme = root.find('skos:ConceptScheme', ns)
    top_ids = [t.get(RDF_RESOURCE) for t in scheme.findall('skos:hasTopConcept', ns)]
    if not top_ids:
        raise RuntimeError('No top concepts found in ACM CCS scheme')

    visited = set()

    def build_node(cid, depth):
        if cid in visited or cid not in concepts:
            return None
        visited.add(cid)
        c = concepts[cid]
        node = {'n': c['label'], 'u': None, 'c': []}
        if depth < 10:
            for nid in c['narrower']:
                child = build_node(nid, depth + 1)
                if child:
                    node['c'].append(child)
        return node

    tree = []
    for tid in top_ids:
        node = build_node(tid, 0)
        if node:
            tree.append(node)
    return tree


def count_nodes(tree):
    return sum(1 + count_nodes(n['c']) for n in tree)


if __name__ == '__main__':
    math_tree = build_msc_tree()
    print(f'Mathematics (MSC2020): {count_nodes(math_tree)} nodes, {len(math_tree)} top divisions')

    physh_tree = build_physh_tree()
    print(f'Physics (PhySH): {count_nodes(physh_tree)} nodes, {len(physh_tree)} disciplines')

    ccs_tree = build_ccs_tree()
    print(f'Computer Science (full ACM CCS): {count_nodes(ccs_tree)} nodes, {len(ccs_tree)} top areas')

    with open('math-tree.json', 'w', encoding='utf-8') as f:
        json.dump(math_tree, f, ensure_ascii=False)
    with open('physics-tree.json', 'w', encoding='utf-8') as f:
        json.dump(physh_tree, f, ensure_ascii=False)
    with open('cs-tree.json', 'w', encoding='utf-8') as f:
        json.dump(ccs_tree, f, ensure_ascii=False)
    print('Wrote math-tree.json, physics-tree.json, cs-tree.json')
