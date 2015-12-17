import collections
import itertools
import random

from causality.dseparation import AbstractGroundGraph
from causality.model.RelationalDependency import RelationalVariable, RelationalDependency
from causality.modelspace import RelationalSpace
from shlee.RCDLight import PDAG, Ancestral, MeekRules
from shlee.RCDLight import RCDLight


class RCDLightPrime(RCDLight):
    def __init__(self, schema, ci_tester, hop_threshold):
        RCDLight.__init__(self, schema, ci_tester, hop_threshold)

    def orient_dependencies(self, background_knowledge=None, truth=None):
        self.phase_2(background_knowledge, truth)

        # Post
        self._update_oriented_dependencies()

    def _update_oriented_dependencies(self):
        self.oriented_dependencies = set()
        for effect, causes in self.parents.items():
            for cause in causes:
                dep = RelationalDependency(cause, effect)
                rev = dep.reverse()
                if rev.relVar1 not in self.parents[rev.relVar2]:
                    self.oriented_dependencies.add(dep)

    def enumerate_unshielded_triples(self):
        # TODO group by attribute classes
        def two_dependencies():
            for d_yx in self.undirected_dependencies:
                for d_zy in self.undirected_dependencies:
                    if d_zy.relVar2.attrName == d_yx.relVar1.attrName:
                        yield d_yx, d_zy

        for d_yx, d_zy in two_dependencies():
            Vx = d_yx.relVar2
            Qy, Rz = d_yx.relVar1, d_zy.relVar1
            for QR in AbstractGroundGraph.extendPath(self.schema, Qy.path, Rz.path):
                QRz = RelationalVariable(QR, Rz.attrName)
                if QRz != Vx and QRz not in self.parents[Vx]:
                    yield QRz, Qy, Vx

    def phase_2(self, background_knowledge=None, truth=None):
        # TODO combine CDG and ancestral relationship
        non_colliders = set()

        unshielded_triples = list(set(self.enumerate_unshielded_triples()))
        random.shuffle(unshielded_triples)
        # if S is recorded in sepsets such that QRz _||_ Vx | S, such unshielded triples will be considered first.
        unshielded_triples.sort(key=lambda ut: frozenset({ut[0], ut[2]}) in self.sepsets, reverse=True)

        # initialize a class dependency graph
        CDG = PDAG()
        CDG.add_edges((c.attrName, e.attrName) for e, cs in self.parents.items() for c in cs)
        ancestral_relationships = Ancestral(CDG.vertices())
        if background_knowledge is not None:
            CDG.orients((x, y) for x, y in background_knowledge)
            RCDLight.__apply_sound_rules(CDG, non_colliders, ancestral_relationships)
            RCDLightPrime.sync(CDG, ancestral_relationships)

        while unshielded_triples:
            rv1, rv2, crv3 = unshielded_triples.pop(0)
            z, y, x = rv1.attrName, rv2.attrName, crv3.attrName

            if CDG.is_oriented(z, y) and CDG.is_oriented(x, y):  # Already oriented
                continue
            if (y, frozenset({x, z})) in non_colliders:  # Already non-collider
                continue
            if z in CDG.de(x):  # delegate to its complement UT.
                continue
            if CDG.is_oriented_as(y, x) or CDG.is_oriented_as(y, z):  # It's an inactive non-collider
                continue

            sepset = self.find_record_and_return_sepset(rv1, crv3, 'Phase II')
            if sepset is not None:
                if rv2 not in sepset:  # collider
                    CDG.orient(z, y)
                    CDG.orient(x, y)
                elif x == z:  # non-collider, RBO
                    CDG.orient(y, x)
                else:
                    non_colliders.add((y, frozenset({x, z})))
            else:
                # z in CDG.de(x)
                if CDG.is_adj(x, z):
                    CDG.orient(x, z)
                else:
                    ancestral_relationships.add(x, z)

            # Update information
            RCDLightPrime.sync(CDG, ancestral_relationships)
            RCDLight.__apply_sound_rules(CDG, non_colliders, ancestral_relationships)
            RCDLightPrime.sync(CDG, ancestral_relationships)

        RCDLightPrime.sync(CDG, ancestral_relationships)
        before = len(CDG.oriented())
        self._update_parents(CDG)
        self._update_oriented_dependencies()
        self.ancestral_relationship_retriever(ancestral_relationships)
        RCDLightPrime.sync(CDG, ancestral_relationships)
        self._update_parents(CDG)
        self._update_oriented_dependencies()
        RCDLight.__apply_sound_rules(CDG, non_colliders, ancestral_relationships)
        RCDLightPrime.sync(CDG, ancestral_relationships)
        after = len(CDG.oriented())
        if after > before:
            print(after - before, 'more oriented')
        # Can we find more ancestral relationships?
        # [Ix].X _||_ P.Y | S (where P.Y not adjacent to [Ix].X), if no sepset found among subsets of adj of [Ix].X)

        # Post Update information
        CDG = RCDLight.complete_rules(CDG, non_colliders, ancestral_relationships, truth)
        after2 = len(CDG.oriented())
        self._update_parents(CDG)
        if after2 > after:
            print(after2 - after, 'more more oriented')

    @staticmethod
    def sync(pdag: PDAG, ancestral_relationships: Ancestral):
        ancestral_relationships.adds(pdag.oriented())
        for x, y in pdag.unoriented():
            if ancestral_relationships.related(x, y):
                pdag.orient(x, y) if x in ancestral_relationships.ans[y] else pdag.orient(y, x)

    def ancestral_relationship_retriever(self, ancestral_relationships):
        isCI = self.ci_tester.isConditionallyIndependent
        self._update_oriented_dependencies()

        crvs = RelationalSpace.getRelationalVariables(self.schema, 0)
        true_causes_of = collections.defaultdict(set)
        spurious_causes_of = collections.defaultdict(set)
        for crv in crvs:
            for cause in self.parents[crv]:
                if RelationalDependency(cause, crv) in self.oriented_dependencies:
                    true_causes_of[crv].add(cause)
                else:
                    spurious_causes_of[crv].add(cause)

        tested_deps = set(RelationalSpace.getRelationalDependencies(self.schema, self.hop_threshold))
        disconnected_deps = tested_deps - set(self.undirected_dependencies)
        for disconnected_dep in disconnected_deps:
            noncause, crv = disconnected_dep.relVar1, disconnected_dep.relVar2
            if frozenset({noncause, crv}) in self.sepsets:
                continue
            x, y = noncause.attrName, crv.attrName
            if ancestral_relationships.related(x, y):
                continue

            spurious = spurious_causes_of[crv]
            causes = true_causes_of[crv]
            assert noncause not in (spurious | causes)
            found = False
            for d in range(len(spurious)):
                for spurious_subset in itertools.combinations(spurious, d):
                    sepset_candidate = tuple(set(spurious_subset) | causes)
                    ci_key = (noncause, crv, tuple(sorted(list(sepset_candidate))))
                    if ci_key not in self.ci_cache:
                        self.ci_cache[ci_key] = isCI(noncause, crv, sepset_candidate)
                    if self.ci_cache[ci_key]:
                        found = True
                        break
                if found:
                    break
            if not found:
                ancestral_relationships.add(y, x)  # y --> x

    def _update_parents(self, CDG):
        # reflect CDG orientation.
        for effect, causes in self.parents.items():
            for cause in list(causes):
                if CDG.is_oriented_as(effect.attrName, cause.attrName):
                    causes.remove(cause)  # remove if oriented in an opposite direction

    @staticmethod
    def complete_rules(pdag, non_colliders, ancestral_relationships, truth=None):
        if truth is not None:
            true_CDG = PDAG()
            true_CDG.add_edges(truth)
            assert all(ans <= true_CDG.an(x) for x, ans in ancestral_relationships.ans.items())
            assert not any(
                    true_CDG.is_oriented_as(x, y) and true_CDG.is_oriented_as(z, y) for y, (x, z) in non_colliders)

        ords = pdag.oriented()  # (x,y)
        unords = pdag.unoriented()  # {x,y}

        co_dag = PDAG()
        for newords in itertools.product(*[[(x, y), (y, x)] for x, y in unords]):
            newdag = PDAG()
            newdag.add_edges(newords)
            newdag.add_edges(ords)

            # failure to abide by non_colliders
            if any(newdag.is_oriented_as(x, y) and newdag.is_oriented_as(z, y) for y, (x, z) in non_colliders):
                continue

            cached = collections.defaultdict(set)
            for x in newdag.vertices():
                cached[x] = newdag.an(x)

            if not all(ans <= cached[x] for x, ans in ancestral_relationships.ans.items()):
                continue

            co_dag.add_edges(newdag.oriented())

        return co_dag

    def find_sepset(self, cause_rv, effect_crv, d, record='unknown'):
        assert len(effect_crv.path) == 1
        isCI = self.ci_tester.isConditionallyIndependent
        neighbors = set(self.parents[effect_crv]) - {cause_rv}
        if d > len(neighbors):
            return None, False

        for sepset_candidate in itertools.combinations(neighbors, d):
            ci_key = (cause_rv, effect_crv, tuple(sorted(list(sepset_candidate))))

            if ci_key not in self.ci_cache:
                self.ci_record[record] += 1
                self.ci_cache[ci_key] = isCI(cause_rv, effect_crv, sepset_candidate)

            if self.ci_cache[ci_key]:
                self.sepsets[frozenset({cause_rv, effect_crv})] = set(sepset_candidate)
                return set(sepset_candidate), True

        return None, True

    def find_record_and_return_sepset(self, cause_rv, effect_crv, record='unknown'):
        if frozenset({cause_rv, effect_crv}) in self.sepsets:
            return self.sepsets[frozenset({cause_rv, effect_crv})]
        else:
            sepset = None
            for d in itertools.count():
                sepset, tested = self.find_sepset(cause_rv, effect_crv, d, record)
                if sepset is not None:
                    self.sepsets[frozenset({cause_rv, effect_crv})] = sepset
                    break
                if not tested:
                    break
            return sepset

    @staticmethod
    def _apply_rules(pdag: PDAG, non_colliders, ancestral: Ancestral):
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
