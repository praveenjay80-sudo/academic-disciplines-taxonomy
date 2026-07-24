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

    # A single call wrapping the whole tree checks the top-level domain
    # names against each other AND recurses into every descendant exactly
    # once — looping per-domain first and then re-wrapping the whole tree
    # re-walks (and double-reports) every nested duplicate a second time.
    errors = []
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
