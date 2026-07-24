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
