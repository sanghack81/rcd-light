import random
import collections
import itertools

import networkx as nx


class PDAG:
    '''
    A Partially Directed Acyclic Graph, which represets an undirected edge with two edges of opposite direction
    '''

    def __init__(self):
        self.E = set()
        self._Pa = collections.defaultdict(set)
        self._Ch = collections.defaultdict(set)

    def vertices(self):
        return set(self._Pa.keys()) | set(self._Ch.keys())

    def __contains__(self, item):
        return item in self.E

    def an(self, x, at=None):
        if at is None:
            at = set()

        for p in self.pa(x):
            if p not in at:
                at.add(p)
                self.an(p, at)

        return at

    def de(self, x, at=None):
        if at is None:
            at = set()

        for p in self.ch(x):
            if p not in at:
                at.add(p)
                self.de(p, at)

        return at

    def oriented(self):
        ors = set()
        for x, y in self.E:
            if (y, x) not in self.E:
                ors.add((x, y))
        return ors

    def remove_vertex(self, v):
        for x, y in list(self.E):
            if x == v or y == v:
                self.E.remove((x, y))

        self._Pa.pop(v, None)
        self._Ch.pop(v, None)

        for k, values in self._Pa.items():
            if v in values:
                values.remove(v)
        for k, values in self._Ch.items():
            if v in values:
                values.remove(v)

    def copy(self):
        new_copy = PDAG()
        new_copy.E = set(self.E)
        new_copy._Pa = collections.defaultdict(set)
        new_copy._Ch = collections.defaultdict(set)
        for k, vs in self._Pa.items():
            new_copy._Pa[k] = set(vs)
        for k, vs in self._Ch.items():
            new_copy._Ch[k] = set(vs)

        return new_copy

    def is_adj(self, x, y):
        return (x, y) in self.E or (y, x) in self.E

    def add_edges(self, xys):
        for x, y in xys:
            self.add_edge(x, y)

    def add_edge(self, x, y):
        assert x != y
        self.E.add((x, y))
        self._Pa[y].add(x)
        self._Ch[x].add(y)

    def add_undirected_edge(self, x, y):
        assert x != y
        self.add_edge(x, y)
        self.add_edge(y, x)

    def orients(self, xys):
        return any([self.orient(x, y) for x, y in xys])

    def orient(self, x, y):
        if (x, y) in self.E:
            if (y, x) in self.E:
                self.E.remove((y, x))
                self._Pa[x].remove(y)
                self._Ch[y].remove(x)
                return True
        return False

    def is_oriented_as(self, x, y):
        return (x, y) in self.E and (y, x) not in self.E

    def is_unoriented(self, x, y):
        return (x, y) in self.E and (y, x) in self.E

    def is_oriented(self, x, y):
        return ((x, y) in self.E) ^ ((y, x) in self.E)

    def ne(self, x):
        # neighbor
        return self._Pa[x] & self._Ch[x]

    def adj(self, x):
        # adjacent
        return self._Pa[x] | self._Ch[x]

    def pa(self, x):
        return self._Pa[x] - self._Ch[x]

    def ch(self, x):
        return self._Ch[x] - self._Pa[x]

    def rule_based_orient(self, ncs, counter=None):
        if counter is None:
            counter = collections.defaultdict(lambda: 0)
        ncs = set(ncs)

        self.run_chained_sncs(ncs, counter)
        changed = True
        while changed:
            changed = False
            # MR2
            changed |= self.run_mr2(counter)

            for non_collider in list(ncs):
                y, (x, z) = non_collider
                # deletable?
                if self.is_oriented(y, x) and self.is_oriented(z, y):
                    ncs.remove(non_collider)
                    continue
                if self.is_oriented_as(y, x) or self.is_oriented_as(y, z):
                    ncs.remove(non_collider)
                    continue
                # MR1, # & SNC-rule 1
                changed |= self.run_mr1(x, y, z, counter)
                changed |= self.run_mr3(x, y, z, counter)
                changed |= self.run_mr4(x, y, z, counter)
                changed |= self.run_snc_r2(x, y, z, counter)

    def run_chained_sncs(self, non_colliders, counter):
        changed = False
        both_side_ncs = [(x, y, z) for b, (a, c) in non_colliders for x, y, z in ((a, b, c), (c, b, a))]
        g = nx.DiGraph()
        # node
        for x, y, z in both_side_ncs:
            g.add_node((x, y, z))
        # edge
        for x, y, z in both_side_ncs:
            for a, b, c in both_side_ncs:
                if (y, z) == (a, b):
                    g.add_edge((x, y, z), (a, b, c))

        vs = nx.algorithms.topological_sort(g, reverse=True)
        desc = collections.defaultdict(set)
        for v in vs:
            chs = set(g.successors(v))
            desc[v] |= chs
            for c in chs:
                desc[v] |= desc[c]

        for x, y, z in both_side_ncs:
            # assert desc[(x, y, z)] == set(nx.algorithms.descendants(g, (x, y, z)))
            for a, b, c in desc[(x, y, z)]:  # nx.algorithms.descendants(g, (x, y, z)):
                if x == c:
                    changed |= self.count(self.orient(y, x), counter, 'SNC-R3')
                    changed |= self.count(self.orient(b, c), counter, 'SNC-R3')
        return changed

    def run_mr3(self, x, y, z, counter):
        # MR3 x-->w<--z, w--y
        changed = False
        for w in self.ch(x) & self.ch(z) & self.ne(y):
            changed |= self.count(self.orient(y, w), counter, 'MR3')
        return changed

    def run_mr2(self, counter):
        changed = False
        for x, y in list(self.E):
            if self.is_unoriented(x, y):  # will check y,x, too
                if self.ch(x) & self.pa(y):  # x-->w-->y
                    changed |= self.count(self.orient(x, y), counter, 'CA')
        return changed

    def run_snc_r2(self, x, y, z, counter):
        # SNC-rule 2
        if self.is_oriented_as(x, z):
            return self.count(self.orient(y, z), counter, 'SNC-R2')
        elif self.is_oriented_as(z, x):
            return self.count(self.orient(y, x), counter, 'SNC-R2')
        return False

    def run_mr4(self, x, y, z, counter):
        # MR4 z-->w-->x # y-->x
        if self.ch(z) & self.pa(x):
            return self.count(self.orient(y, x), counter, 'MR4')
        elif self.ch(x) & self.pa(z):  # z<--w<--x, z<--y
            return self.count(self.orient(y, z), counter, 'MR4')
        return False

    def run_mr1(self, x, y, z, counter):
        if self.is_oriented_as(x, y):
            return self.count(self.orient(y, z), counter, 'KNC')
        elif self.is_oriented_as(z, y):
            return self.count(self.orient(y, x), counter, 'KNC')
        return False

    def count(self, result, counter, name):
        if result:
            counter[name] += 1
        return result

    def complete(self, non_colliders, counter=None):
        '''
        Completely orient a PDAG only when all non-colliders are provided.
        '''
        if counter is None:
            counter = collections.defaultdict(lambda: 0)

        failed = set()
        orientables = set()
        for x, y in self.E:
            if (y, x) in self.E:
                orientables.add((x, y))
                orientables.add((y, x))

        for x, y in list(orientables):
            if (x, y) not in orientables:
                continue

            orienting_g = self.copy()
            orienting_g.orient(x, y)
            if dor_and_tarsi_2(orienting_g, non_colliders):
                orientables -= orienting_g.E
            else:
                failed.add((x, y))
                orientables.discard((y, x))

        for x, y in failed:
            self.count(self.orient(y, x), counter, 'DT')

        return not bool(failed), failed


def dor_and_tarsi_2(orienting_g, non_colliders):
    g = orienting_g.copy()
    while g.vertices():
        # shuffling would be helpful to cover unoriented edges but not necessary
        sinkables = list(filter(lambda v: not g.ch(v), g.vertices()))
        random.shuffle(sinkables)
        for sink in sinkables:
            sink_ne = g.ne(sink)
            sink_adjs = g.adj(sink)
            no_new_vee = all(all(g.is_adj(ne, adj) for adj in sink_adjs - {ne}) for ne in sink_ne)
            if no_new_vee:
                for v1, v2 in itertools.combinations(g.adj(sink), 2):
                    if (sink, frozenset({v1, v2})) in non_colliders:
                        break
                else:
                    for ne in sink_ne:
                        orienting_g.orient(ne, sink)
                    g.remove_vertex(sink)
                    break  # sink has found.
        else:  # if there is no sink.
            return False
    return True


class RCDLOrientationRules:
    @classmethod
    def generate_DAG(cls, size=10):
        assert size >= 0
        gg = nx.DiGraph()
        vs = list(range(size))
        gg.add_nodes_from(vs)
        edges = list(itertools.combinations(vs, 2))
        gg.add_edges_from(random.sample(edges, random.randrange(0, len(edges))))
        # random.shuffle(edges)
        # n_edges = random.randrange(0, len(edges))
        # gg.add_edges_from(edges[:n_edges])
        return gg

    @classmethod
    def pattern(cls, graph: nx.DiGraph):
        pdag = PDAG()
        # skeleton
        for x, y in graph.edges_iter():
            pdag.add_undirected_edge(x, y)

        for v in graph.nodes_iter():
            # collider, x --> v <-- y
            for x, y in itertools.combinations(graph.predecessors(v), 2):
                # unshielded
                if not graph.has_edge(x, y) and not graph.has_edge(y, x):
                    pdag.orient(x, v)
                    pdag.orient(y, v)
        return pdag

    @classmethod
    def generate_and_orient_background_knowledge(cls, graph: nx.DiGraph, pdag: PDAG):
        # this includes possible: RBO, shielded colliders, and traditional background knowledge, etc
        ee = list(graph.edges())
        # random.shuffle(ee)
        # TODO prefer small?
        if ee:
            for e in random.sample(ee, random.randrange(0, len(ee))):
                x, y = e
                pdag.orient(x, y)

    @classmethod
    def generate_non_colliders(cls, graph: nx.DiGraph):
        non_colliders = set()
        threshold = random.random()
        for v in graph.nodes_iter():
            ne_v = list(itertools.chain(graph.successors(v), graph.predecessors(v)))
            for x, y in itertools.combinations(ne_v, 2):
                if not (graph.has_edge(x, v) and graph.has_edge(y, v)):  # non_collider
                    # unshielded, all!
                    if not graph.has_edge(x, y) and not graph.has_edge(y, x):
                        non_colliders.add((v, frozenset({x, y})))
                    else:
                        if random.random() <= threshold:  # shielded
                            non_colliders.add((v, frozenset({x, y})))
        return non_colliders


# random.seed(0)
if __name__ == "__main__":
    for i in itertools.count(start=1):
        if i % 1000 == 0:
            print("{}-th instances".format(i))

        # dag = RCDLOrientationRules.generate_DAG(random.randrange(4, 12))
        dag = RCDLOrientationRules.generate_DAG(7)
        pdag = RCDLOrientationRules.pattern(dag)  # all vee-structures oriented
        RCDLOrientationRules.generate_and_orient_background_knowledge(dag, pdag)
        ncs = RCDLOrientationRules.generate_non_colliders(dag)  # randomly generated SNCs
        pdag.rule_based_orient(ncs)
        comp, failed = pdag.complete(ncs)
        assert not (pdag.oriented() - set(dag.edges()))
        # if not comp and pdag.oriented() - set(dag.edges()):
        #     print('failed {}'.format(failed))
        #     print('ncs {}'.format(ncs))
        #     print(dag.edges())
        #     print(pdag.oriented())
        #     print('unoriented {}'.format(set(dag.edges()) - pdag.oriented()))
        #     print('misoriented {}'.format(pdag.oriented() - set(dag.edges())))
        #     exit()
