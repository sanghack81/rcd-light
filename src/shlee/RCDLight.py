# Copyright 2015 Sanghack Lee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import collections
import itertools
import numbers
import random

from causality.dseparation import AbstractGroundGraph
from causality.model.Model import Model
from causality.model.RelationalDependency import RelationalVariable, RelationalDependency
from causality.model.Schema import Schema
from causality.modelspace import RelationalSpace


# An Improved RCD-Light algorithm
# based on "On Learning Causal Models from Relational Data (In Proc. of AAAI-2016)"
# Sanghack Lee & Vasant Honavar
#
# This algorithm is compatible with Relational Causal Discovery (RCD) from
# "A Sound and Complete Algorithm for Learning Causal Models from Relational Data" (In Proc. of UAI-2013)
#
class RCDLight(object):
    def __init__(self, schema, ci_tester, hop_threshold):
        if not isinstance(hop_threshold, numbers.Integral) or hop_threshold < 0:
            raise Exception("Hop threshold must be a non-negative integer: found {}".format(hop_threshold))

        self._schema = schema
        self._ci_tester = ci_tester
        self._hop_threshold = hop_threshold
        self._ci_cache = dict()
        self._sepsets = dict()
        self._causes = None
        self.undirectedDependencies = None
        self.orientedDependencies = None
        self.ciRecord = collections.defaultdict(lambda: 0)

    def identifyUndirectedDependencies(self):
        '''
        This is for the Phase I of RCD-Light.
        '''
        potential_deps = RelationalSpace.getRelationalDependencies(self._schema, self._hop_threshold)

        keyfunc = lambda dep: dep.relVar2
        self._causes = {effect: set(cause.relVar1 for cause in causes)
                        for effect, causes in
                        itertools.groupby(sorted(potential_deps, key=keyfunc), key=keyfunc)}

        to_be_tested = set(potential_deps)
        for d in itertools.count():
            for dep in list(to_be_tested):  # remove-safe loop
                if dep not in to_be_tested:
                    continue

                cause, effect = dep.relVar1, dep.relVar2
                sepset, tested = self._find_sepset_with_size(cause, effect, d, 'Phase I')
                if not tested:
                    to_be_tested.remove(dep)
                if sepset is not None:
                    dep_reversed = dep.reverse()
                    to_be_tested -= {dep, dep_reversed}
                    self._causes[dep.relVar2].remove(dep.relVar1)
                    self._causes[dep_reversed.relVar2].remove(dep_reversed.relVar1)
            if not to_be_tested:
                break

        self.undirectedDependencies = {RelationalDependency(c, e) for e, cs in self._causes.items() for c in cs}
        return set(self.undirectedDependencies)

    def _enumerate_RUTs(self):
        '''
        This enumerates all representative unshielded triples.
        '''

        def two_dependencies():
            for d_yx in self.undirectedDependencies:
                for d_zy in self.undirectedDependencies:
                    if d_zy.relVar2.attrName == d_yx.relVar1.attrName:
                        yield d_yx, d_zy

        for d_yx, d_zy in two_dependencies():
            Vx = d_yx.relVar2  # this is a canonical relational variable
            Qy, Rz = d_yx.relVar1, d_zy.relVar1
            for QR in AbstractGroundGraph.extendPath(self._schema, Qy.path, Rz.path):
                QRz = RelationalVariable(QR, Rz.attrName)
                if QRz != Vx and QRz not in self._causes[Vx]:
                    yield QRz, Qy, Vx

    def orientDependencies(self, background_knowledge=None):
        '''
        This is Phase II of RCD-Light.
         This orients dependencies based on both
         (i) CI-based orientation and;
         (ii) constraints-based orientation.
        '''
        assert self.undirectedDependencies is not None

        # initialize attribute class level non-colliders
        non_colliders = set()
        # initialize class dependency graph
        cdg = PDAG((c.attrName, e.attrName) for e, cs in self._causes.items() for c in cs)
        ancestrals = Ancestral(cdg.vertices())
        if background_knowledge is not None:
            cdg.orients(background_knowledge)
            RCDLight._apply_rules(cdg, non_colliders, ancestrals)

        # enumerate all representative unshielded triples
        ruts = list(set(self._enumerate_RUTs()))
        random.shuffle(ruts)
        # take advantage of cached CIs
        ruts.sort(key=lambda ut: frozenset({ut[0], ut[2]}) in self._sepsets,
                  reverse=True)

        for rv1, rv2, crv3 in ruts:
            z, y, x = rv1.attrName, rv2.attrName, crv3.attrName

            # Check skippable tests
            if cdg.is_oriented(z, y) and cdg.is_oriented(x, y):  # already oriented
                continue
            if (y, frozenset({x, z})) in non_colliders:  # already non-collider
                continue
            if z in cdg.de(x):  # delegate to its complement UT.
                continue
            if cdg.is_oriented_as(y, x) or cdg.is_oriented_as(y, z):  # an inactive non-collider
                continue

            sepset = self._find_sepset(rv1, crv3, 'Phase II')
            if sepset is not None:
                if rv2 not in sepset:  # collider
                    cdg.orients(((z, y), (x, y)))
                elif x == z:  # non-collider, RBO
                    cdg.orient(y, x)
                else:
                    non_colliders.add((y, frozenset({x, z})))
            else:
                # The original version of RCD-Light orients (or add) an edge as x-->z, and
                # takes advantage of Rule 2.
                # The improved version explicitly represents ancestral relationships, and can
                # orient more edges.
                cdg.orient(x, z) if cdg.is_adj(x, z) else ancestrals.add(x, z)

            RCDLight._apply_rules(cdg, non_colliders, ancestrals)

        #
        self._reflect_orientations(cdg)
        self._update_oriented_dependencies()
        return set(self.orientedDependencies)

    def _reflect_orientations(self, cdg):
        for effect, causes in self._causes.items():
            for cause in list(causes):
                if cdg.is_oriented_as(effect.attrName, cause.attrName):
                    causes.remove(cause)

    def _update_oriented_dependencies(self):
        self.orientedDependencies = set()
        for effect, causes in self._causes.items():
            for cause in causes:
                dep = RelationalDependency(cause, effect)
                rev = dep.reverse()
                if rev.relVar1 not in self._causes[rev.relVar2]:
                    self.orientedDependencies.add(dep)

    @staticmethod
    def _apply_rules(pdag, non_colliders, ancestral):
        '''
        Orients unoriented edges in a PDAG given an explicit, but may not complete, list of non-colliders and
          an additional ancestral relationship among vertices.
        '''
        # colliders are not all oriented.
        # non-colliders are imperfect.
        # ancestral relationships are imperfect.
        changed = True
        while changed:
            changed = False

            changed |= MeekRules.rule_2(pdag)
            for y, (x, z) in non_colliders:
                changed |= MeekRules.rule_1(pdag, x, y, z)
                changed |= MeekRules.rule_3(pdag, x, y, z)
                changed |= MeekRules.rule_4(pdag, x, y, z)

                if (x, z) in ancestral:
                    changed |= pdag.orient(y, z)
                elif (z, x) in ancestral:
                    changed |= pdag.orient(y, x)

    def _find_sepset_with_size(self, rv1, rv2, size, record='unknown'):
        assert len(rv2.path) == 1
        is_ci = self._ci_tester.isConditionallyIndependent

        neighbors = set(self._causes[rv2]) - {rv1}
        if size > len(neighbors):
            return None, False

        for condition in itertools.combinations(neighbors, size):
            ci_key = (rv1, rv2, tuple(sorted(list(condition))))

            if ci_key not in self._ci_cache:
                self.ciRecord[record] += 1
                self.ciRecord['total'] += 1
                self._ci_cache[ci_key] = is_ci(rv1, rv2, condition)

            if self._ci_cache[ci_key]:
                self._sepsets[frozenset({rv1, rv2})] = set(condition)
                return set(condition), True

        return None, True

    def _find_sepset(self, rv1, rv2, record='unknown'):
        assert len(rv2.path) == 1
        key = frozenset({rv1, rv2})
        if key in self._sepsets:
            return self._sepsets[key]

        for d in itertools.count():
            sepset, tested = self._find_sepset_with_size(rv1, rv2, d, record)
            if sepset is not None:
                self._sepsets[key] = sepset
                return sepset
            if not tested:
                return None


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


def runRCDLight(schema, citest, hopThreshold):
    rcdl = RCDLight(schema, citest, hopThreshold)
    rcdl.identifyUndirectedDependencies()
    rcdl.orientDependencies()
    return rcdl.orientedDependencies



# This example is given in the AAAI paper
def incompleteness_example():
    schema = Schema()
    schema.addEntity("E1")
    schema.addEntity("E2")
    schema.addEntity("E3")
    schema.addRelationship("R1", ("E1", Schema.ONE), ("E2", Schema.ONE))
    schema.addRelationship("R2", ("E2", Schema.ONE), ("E3", Schema.ONE))
    schema.addRelationship("R3", ("E2", Schema.ONE), ("E3", Schema.ONE))
    schema.addAttribute("R1", "X")
    schema.addAttribute("R2", "Y")
    schema.addAttribute("E2", "Z")

    d1 = RelationalDependency(RelationalVariable(["R2", "E2", "R1"], "X"), RelationalVariable(["R2"], "Y"))
    d2 = RelationalDependency(RelationalVariable(["R2", "E3", "R3", "E2"], "Z"), RelationalVariable(["R2"], "Y"))
    d3 = RelationalDependency(RelationalVariable(["R1", "E2", "R2", "E3", "R3", "E2"], "Z"),
                              RelationalVariable(["R1"], "X"))
    model = Model(schema, [d1, d2, d3])
    return schema, model
