"""Run with python3 tests/test_ancestral.py; no original RCD installation needed."""

import ast
import collections
from itertools import permutations
from pathlib import Path


# This repository overlays the original RCD distribution. Load its standalone
# graph helpers verbatim without importing the unavailable upstream modules.
source = Path(__file__).resolve().parents[1] / 'src/shlee/RCDLight.py'
tree = ast.parse(source.read_text())
names = {'Ancestral', 'PDAG', 'MeekRules', 'RCDLight'}
tree.body = [node for node in tree.body
             if isinstance(node, ast.ClassDef) and node.name in names]
namespace = {'collections': collections}
exec(compile(tree, str(source), 'exec'), namespace)
Ancestral, PDAG, RCDLight = (namespace[name] for name in
                           ('Ancestral', 'PDAG', 'RCDLight'))


def test_ancestral():
    vertices = 'ABCD'
    expected = {(x, y) for x in vertices for y in vertices if x < y}
    for edges in permutations([('A', 'B'), ('B', 'C'), ('C', 'D')]):
        ancestral = Ancestral(vertices)
        ancestral.adds(edges)
        ancestral.add('A', 'B')  # Adding a known relation is harmless.
        assert {(x, y) for x in vertices for y in vertices
                if (x, y) in ancestral} == expected
        assert {(x, y) for x in vertices for y in ancestral.des[x]} == expected
        assert ancestral.related('A', 'D') and ancestral.related('D', 'A')

    graph = PDAG([('A', 'Y'), ('Y', 'A'), ('Y', 'D'), ('D', 'Y')])
    RCDLight._apply_rules(graph, {('Y', frozenset({'A', 'D'}))}, ancestral)
    assert graph.is_oriented_as('Y', 'D')
    assert graph.is_unoriented('A', 'Y')


if __name__ == '__main__':
    test_ancestral()
    print('Ancestral regression checks passed.')
