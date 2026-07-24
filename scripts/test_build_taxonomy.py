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
