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


if __name__ == '__main__':
    unittest.main()
