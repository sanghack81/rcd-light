import collections
import itertools
import random

import networkx as nx


class Ancestral:
    '''
    Record ancestral relationships (or equivalently, partially ordered)
    '''

    def __init__(self, vs):
        self.vs = set(vs)
        self.ans = collections.defaultdict(set)
        self.des = collections.defaultdict(set)

    def related(self, x, y):
        '''
        check either two vertices are partially ordered
        :param x:
        :param y:
        :return:
        '''
        assert x != y
        return y in self.ans[x] or y in self.des[x]

    def adds(self, ancs):
        for anc, x in ancs:
            self.add(anc, x)

    def add(self, ancestor, x):
        assert ancestor != x
        assert x not in self.ans[ancestor]
        if ancestor in self.ans[x]:
            return

        dedes = self.des[x]
        anans = self.ans[ancestor]

        for dede in dedes:
            self.ans[dede] |= anans
        self.ans[x] |= anans

        for anan in anans:
            self.des[anan] |= dedes
        self.des[ancestor] |= dedes

    def __contains__(self, item):
        x, y = item  # x-...->y
        return x in self.ans[y]


class PDAG:
    '''
    A Partially Directed Acyclic Graph.
    '''

    def __init__(self, edges=None):
        self.E = set()
        self._Pa = collections.defaultdict(set)
        self._Ch = collections.defaultdict(set)
        if edges is not None:
            self.add_edges(edges)

    def vertices(self):
        return set(self._Pa.keys()) | set(self._Ch.keys())

    def __contains__(self, item):
        return item in self.E

    # Ancestors
    def an(self, x, at=None):
        if at is None:
            at = set()

        for p in self.pa(x):
            if p not in at:
                at.add(p)
                self.an(p, at)

        return at

    # Descendants
    def de(self, x, at=None):
        if at is None:
            at = set()

        for p in self.ch(x):
            if p not in at:
                at.add(p)
                self.de(p, at)

        return at

    # get all oriented edges
    def oriented(self):
        ors = set()
        for x, y in self.E:
            if (y, x) not in self.E:
                ors.add((x, y))
        return ors

    def unoriented(self):
        uors = set()
        for x, y in self.E:
            if (y, x) in self.E:
                uors.add(frozenset({x, y}))
        return uors

    # remove a vertex
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

    # Adjacent
    def is_adj(self, x, y):
        return (x, y) in self.E or (y, x) in self.E

    def add_edges(self, xys):
        for x, y in xys:
            self.add_edge(x, y)

    def add_edge(self, x, y):
        '''
        if y-->x exists, adding x-->y makes x -- y.
        :param x:
        :param y:
        :return:
        '''
        assert x != y
        self.E.add((x, y))
        self._Pa[y].add(x)
        self._Ch[x].add(y)

    def add_undirected_edge(self, x, y):
        # will override any existing directed edge
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

    # get neighbors
    def ne(self, x):
        return self._Pa[x] & self._Ch[x]

    # get adjacent vertices
    def adj(self, x):
        return self._Pa[x] | self._Ch[x]

    # get parents
    def pa(self, x):
        return self._Pa[x] - self._Ch[x]

    # get children
    def ch(self, x):
        return self._Ch[x] - self._Pa[x]

    def rule_based_orient(self, ncs, counter=None):
        if counter is None:
            counter = collections.defaultdict(lambda: 0)
        ncs = set(ncs)
        before = sum(counter.values())
        self.run_chained_sncs(ncs, counter)
        changed = True
        while changed:
            changed = False
            # MR2
            changed |= MeekRules.rule_2(counter)

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
                changed |= MeekRules.rule_1(x, y, z, counter)
                changed |= MeekRules.rule_3(x, y, z, counter)
                changed |= MeekRules.rule_4(x, y, z, counter)
                changed |= self.run_snc_r2(x, y, z, counter)
        return before != sum(counter.values())

    def rule_based_orient_for_rcdl(self, non_colliders, counter=None):
        if counter is None:
            counter = collections.defaultdict(lambda: 0)
        non_colliders = set(non_colliders)
        before = sum(counter.values())
        changed = True
        while changed:
            changed = False
            # MR2
            changed |= MeekRules.rule_2(counter)

            for non_collider in list(non_colliders):
                y, (x, z) = non_collider
                # if both oriented
                if self.is_oriented(y, x) and self.is_oriented(z, y):
                    non_colliders.remove(non_collider)
                    continue
                # inactive
                if self.is_oriented_as(y, x) or self.is_oriented_as(y, z):
                    non_colliders.remove(non_collider)
                    continue
                # MR1, 3, and 4
                changed |= MeekRules.rule_1(x, y, z, counter)
                changed |= MeekRules.rule_3(x, y, z, counter)
                changed |= MeekRules.rule_4(x, y, z, counter)
        return before != sum(counter.values())

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

    def run_snc_r2(self, x, y, z, counter):
        # SNC-rule 2
        if self.is_oriented_as(x, z):
            return self.count(self.orient(y, z), counter, 'SNC-R2')
        elif self.is_oriented_as(z, x):
            return self.count(self.orient(y, x), counter, 'SNC-R2')
        return False

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
            if PDAG_extensibility(orienting_g, non_colliders):
                orientables -= orienting_g.E
            else:
                failed.add((x, y))
                orientables.discard((y, x))

        for x, y in failed:
            self.count(self.orient(y, x), counter, 'DT')

        return not bool(failed), failed


class MeekRules:
    @staticmethod
    # x--y--z must be a (shielded or unshielded) non-colider
    def rule_3(pdag: PDAG, x, y, z):
        # MR3 x-->w<--z, w--y
        changed = False
        for w in pdag.ch(x) & pdag.ch(z) & pdag.ne(y):
            changed |= pdag.orient(y, w)
        return changed

    @staticmethod
    def rule_2(pdag: PDAG):
        changed = False
        for x, y in list(pdag.E):
            if pdag.is_unoriented(x, y):  # will check y,x, too
                if pdag.ch(x) & pdag.pa(y):  # x-->w-->y
                    changed |= pdag.orient(x, y)
        return changed

    @staticmethod
    # x--y--z must be a (shielded or unshielded) non-colider
    def rule_4(pdag: PDAG, x, y, z):
        # MR4 z-->w-->x # y-->x
        if pdag.ch(z) & pdag.pa(x):
            return pdag.orient(y, x)
        elif pdag.ch(x) & pdag.pa(z):  # z<--w<--x, z<--y
            return pdag.orient(y, z)
        return False

    @staticmethod
    # x--y--z must be a (shielded or unshielded) non-colider
    def rule_1(pdag: PDAG, x, y, z):
        if pdag.is_oriented_as(x, y):
            return pdag.orient(y, z)
        elif pdag.is_oriented_as(z, y):
            return pdag.orient(y, x)
        return False


def PDAG_extensibility(orienting_g, non_colliders):
    '''
    Test whether a given PDAG admits a DAG satisying all non-colliders.
    All unshielded colliders must be oriented.
    Any unshielded triple which is not fully oriented will be treated as unshielded non-colliders.
    All shielded non-colliders must be explicitly provided in non-colliders.
    :param orienting_g:
    :param non_colliders:
    :return:
    '''
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
