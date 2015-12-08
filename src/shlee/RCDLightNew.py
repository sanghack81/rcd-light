import itertools
import numbers
import logging
import random
import collections

from causality.citest.CITest import Oracle
from causality.dseparation import AbstractGroundGraph
from causality.model.Model import Model
from causality.model.RelationalDependency import RelationalVariable, RelationalDependency
from causality.model.Schema import Schema
from causality.modelspace import RelationalSpace
from shlee.snc_rules import PDAG

logger = logging.getLogger(__name__)

CONSIDER_NO_DUPLICATE_RELATIONSHIP = True


class SchemaDependencyWrapper:
    def __init__(self, schema, dependencies):
        self.schema = schema
        self.dependencies = dependencies


# Will not be compatible with RCD light
class RCDLightNew(object):
    def __init__(self, schema, ci_tester, hop_threshold, depth=None):
        if not isinstance(hop_threshold, numbers.Integral) or hop_threshold < 0:
            raise Exception("Hop threshold must be a non-negative integer: found {}".format(hop_threshold))
        if depth is not None and (not isinstance(depth, numbers.Integral) or depth < 0):
            raise Exception("Depth must be a non-negative integer or None: found {}".format(depth))

        if isinstance(ci_tester, Oracle):
            logger.warning("abstract ground graph is known to be not sound and complete. Use with caution.")

        # Configurations
        self.schema = schema
        self.ci_tester = ci_tester
        self.hop_threshold = hop_threshold
        self.depth = depth
        # Cached information
        self.ci_cache = dict()
        self.sepsets = dict()
        # Inner structures
        self.parents = None
        self.non_colliders = set()
        # Results
        self.undirected_dependencies = None
        self.oriented_dependencies = None
        self.edge_orientation_rule_frequency = collections.defaultdict(lambda: 0)
        self.ci_record = collections.defaultdict(lambda: 0)

    def identify_undirected_dependencies(self):
        deps = RelationalSpace.getRelationalDependencies(self.schema, self.hop_threshold, includeExistence=False)
        self.ci_record['num_poten'] = len(deps)

        keyfunc = lambda d: d.relVar2
        self.parents = {k: set(g.relVar1 for g in gs) for k, gs in
                        itertools.groupby(sorted(deps, key=keyfunc), key=keyfunc)}

        if self.depth is None:
            self.depth = max(len(v) for v in self.parents.values())

        to_be_tested = set(deps)
        for d in range(self.depth + 1):
            if not to_be_tested:
                break
            # remove-safe loop
            for dependency in list(to_be_tested):
                if dependency not in to_be_tested:
                    continue

                rv1, rv2 = dependency.relVar1, dependency.relVar2
                sepset, tested = self.find_sepset(rv1, rv2, d, 'Phase I')
                if not tested:
                    to_be_tested.remove(dependency)
                if sepset is not None:
                    dep_reversed = dependency.reverse()
                    to_be_tested -= {dependency, dep_reversed}
                    self.parents[dependency.relVar2].remove(dependency.relVar1)
                    self.parents[dep_reversed.relVar2].remove(dep_reversed.relVar1)

        self.undirected_dependencies = {RelationalDependency(c, e) for e, cs in self.parents.items() for c in cs}

    def skip_phase_1(self, dependencies):
        self.undirected_dependencies = set(dependencies) | {d.reverse() for d in dependencies}
        key_func = lambda d: d.relVar2
        self.parents = {k: set(g.relVar1 for g in gs) for k, gs in
                        itertools.groupby(sorted(self.undirected_dependencies, key=key_func), key=key_func)}

    def find_sepset(self, rv1, rv2, d, record='unknown'):
        assert len(rv2.path) == 1
        neighbors = set(self.parents[rv2]) - {rv1}
        any_tested = False
        if d <= len(neighbors):
            for candidate_sepset in itertools.combinations(neighbors, d):
                any_tested = True
                ci_key = (rv1, rv2, tuple(sorted(list(candidate_sepset))))

                if ci_key not in self.ci_cache:
                    self.ci_record[record] += 1
                    self.ci_cache[ci_key] = self.ci_tester.isConditionallyIndependent(rv1, rv2, candidate_sepset)

                if self.ci_cache[ci_key]:
                    self.sepsets[frozenset({rv1, rv2})] = set(candidate_sepset)
                    return set(candidate_sepset), any_tested

        return None, any_tested

    def orient_dependencies(self, background_knowledge=None, old_mode=False, simultaneous=True):
        # Pre
        self.depth = max(len(v) for v in self.parents.values())

        self.phase_2(old_mode, background_knowledge, simultaneous)
        # Post
        self.oriented_dependencies = set()
        for effect, causes in self.parents.items():
            for cause in causes:
                dep = RelationalDependency(cause, effect)
                rev = dep.reverse()
                if rev.relVar1 not in self.parents[rev.relVar2]:
                    self.oriented_dependencies.add(dep)

    def _find_unshielded_triples(self):
        '''
        This generates all possible unshielded triples appeared in ground graphs
        '''

        def two_dependencies():
            for d_yx in self.undirected_dependencies:
                for d_zy in self.undirected_dependencies:
                    if d_zy.relVar2.attrName == d_yx.relVar1.attrName:
                        yield d_yx, d_zy

        for d_yx, d_zy in two_dependencies():
            Qy, Rz = d_yx.relVar1, d_zy.relVar1
            for QR in AbstractGroundGraph.extendPath(self.schema, Qy.path, Rz.path):
                QRz = RelationalVariable(QR, Rz.attrName)
                # Q_prime_y = RelationalVariable(Q_prime, Qy.attrName)
                if QRz != d_yx.relVar2 and QRz not in self.parents[d_yx.relVar2]:
                    yield QRz, Qy, d_yx.relVar2
            # for QR, Q_prime in extend2(self.schema, Qy.path, Rz.path):
            #     QRz = RelationalVariable(QR, Rz.attrName)
            #     Q_prime_y = RelationalVariable(Q_prime, Qy.attrName)
            #     if QRz != d_yx.relVar2 and QRz not in self.parents[d_yx.relVar2]:
            #         yield QRz, Qy, Q_prime_y, d_yx.relVar2

    def phase_2(self, old_mode=False, background_knowledge=None, simultaneous=True):
        # Prepare a set of unshielded triples
        unshielded_triples = list(set(self._find_unshielded_triples()))
        # if old_mode:
        #     unshielded_triples = list(filter(lambda ut: ut[1] == ut[2], unshielded_triples))
        random.shuffle(unshielded_triples)
        # unshielded_triples.sort(key=lambda ut: frozenset({ut[0], ut[3]}) in self.sepsets, reverse=True)
        unshielded_triples.sort(key=lambda ut: frozenset({ut[0], ut[2]}) in self.sepsets, reverse=True)

        self.ci_record['num_rut'] = len(unshielded_triples)
        # Prepare a class dependency graph
        CDG = PDAG()
        CDG.add_edges((c.attrName, e.attrName) for e, cs in self.parents.items() for c in cs)
        if background_knowledge is not None:
            CDG.orients((x, y) for x, y in background_knowledge)

        # Pre Update information
        if simultaneous:
            CDG.rule_based_orient(self.non_colliders, self.edge_orientation_rule_frequency)

        while unshielded_triples:
            # rv1, rv2, rv2_, rv3 = unshielded_triples.pop(0)
            rv1, rv2, rv3 = unshielded_triples.pop(0)
            z, y, x = rv1.attrName, rv2.attrName, rv3.attrName

            # Is skippable?
            if CDG.is_oriented(z, y) and CDG.is_oriented(x, y):
                continue
            if (y, frozenset({x, z})) in self.non_colliders:
                continue
            if z in CDG.de(x):
                continue
            # if rv2 != rv2_ and not rv2.intersects(rv2_):
            #     logger.warning('RCD Oracle is not reliable for this case: {}--{}--{}'.format(rv3, rv2, rv1))
            #     continue



            if x != z and (CDG.is_oriented_as(y, x) or CDG.is_oriented_as(y, z)):
                self.non_colliders.add((y, frozenset({x, z})))
            else:
                sepset = self.find_record_and_return_sepset(rv1, rv3, 'Phase II')
                if sepset is not None:
                    #if rv2 not in sepset and rv2_ not in sepset:  # collider
                    if rv2 not in sepset:  # collider
                        CDG.count(CDG.orient(z, y), self.edge_orientation_rule_frequency, 'CD' if x != z else 'RBO')
                        CDG.count(CDG.orient(x, y), self.edge_orientation_rule_frequency, 'CD' if x != z else 'RBO')
                    elif x == z:  # non-collider, RBO
                        CDG.count(CDG.orient(y, x), self.edge_orientation_rule_frequency, 'RBO')
                    else:
                        self.non_colliders.add((y, frozenset({x, z})))
                else:
                    if CDG.is_adj(x, z):
                        CDG.count(CDG.orient(x, z), self.edge_orientation_rule_frequency, 'NONE_SEPSET')
                    else:
                        CDG.add_edge(x, z)

            # Update information
            if simultaneous:
                CDG.rule_based_orient(self.non_colliders, self.edge_orientation_rule_frequency)

        # Post Update information
        CDG.rule_based_orient(self.non_colliders, self.edge_orientation_rule_frequency)
        CDG.complete(self.non_colliders, self.edge_orientation_rule_frequency)  # essential!

        # reflect CDG orientation.
        for effect, causes in self.parents.items():
            for cause in list(causes):
                if CDG.is_oriented_as(effect.attrName, cause.attrName):
                    causes.remove(cause)  # remove if oriented in an opposite direction

    def find_record_and_return_sepset(self, rv1, rv2, record='unknown'):
        if frozenset({rv1, rv2}) in self.sepsets:
            return self.sepsets[frozenset({rv1, rv2})]
        else:
            sepset = None
            for d in range(self.depth + 1):
                sepset, tested = self.find_sepset(rv1, rv2, d, record)
                if sepset is not None:
                    self.sepsets[frozenset({rv1, rv2})] = sepset
                    break
                if not tested:
                    break
            return sepset


def LLRSP(schema: Schema, P, Q):
    assert P[0] == Q[0]
    min_len = min(len(P), len(Q))
    for i in range(1, min_len):
        if P[i] != Q[i]:
            return i
        if schema.hasRelationship(P[i]) and schema.getRelationship(P[i]).getCardinality(P[i - 1]) == Schema.MANY:
            return i
    return min_len


def join(P, Q):
    assert P[-1] == Q[0]
    return P + Q[1:]


def intersectible(schema, P, Q):
    assert P != Q and len(P) > 0 and len(Q) > 0 and P[0] == Q[0]
    if P[-1] != Q[-1]:
        return False
    min_len = min(len(P), len(Q))
    if P[0:min_len] == Q[0:min_len]:
        return False

    if CONSIDER_NO_DUPLICATE_RELATIONSHIP:
        # TODO RCD (by Maier et al.) only supports 'binary' relationship classes. Following should be changed appropriately.
        is_binary = lambda rel: True
        is_rel = lambda rel: schema.hasRelationship(rel)
        # R,E ,R and R,E',R
        if len(P) == len(Q) == 3 and P[0] == P[2] == Q[0] == Q[2] and P[1] != Q[1] and is_rel(P[0]) and is_binary(
                P[0]):  # P[1] != Q[1] is redundant since P!=Q
            return False
    return LLRSP(schema, P, Q) + LLRSP(schema, P[::-1], Q[::-1]) <= min_len


def extend2(schema: Schema, P, Q):
    '''
    This returns not only extend of P and Q, but also, P' that is equal to P or intersectible with P
    '''
    assert len(P) > 0 and len(Q) > 0
    assert P[-1] == Q[0]
    m = len(P)
    n = len(Q)
    rev_Q = Q[::-1]

    # length shared from the joint.
    l = LLRSP(schema, P[::-1], Q)
    if LLRSP(schema, P[:m - l + 1][::-1], Q[l - 1:]) == 1:
        yield join(P[:m - l + 1], Q[l - 1:]), P

    # TODO RCD (by Maier et al.) only supports 'binary' relationship classes. Following should be changed appropriately.
    is_binary = lambda rel: True
    is_rel = lambda rel: schema.hasRelationship(rel)

    def matching_pairs():
        for i in range(m - l):  # exclude LRSP
            for j in range(n - l):  # exclude LRSP
                if P[i] == rev_Q[j]:
                    yield i, j

    for i, j in matching_pairs():
        A, B = P[:i + 1][::-1], P[i:m - l + 1]  # P  [0, .... [i] .... [m-l] ....] m
        C, D = rev_Q[:j + 1][::-1], rev_Q[j:n - l + 1]  # rQ [0, ... [j] ... [n-l] ....] n

        # Test 'C' part
        if LLRSP(schema, A, C) > 1:
            continue
        if LLRSP(schema, B, C) == len(B):
            continue

        # Test 'D' part
        llrsp_AD = LLRSP(schema, A, D)
        llrsp_BD = LLRSP(schema, B, D)

        if llrsp_AD == len(D):
            continue
        if llrsp_BD > 1 and not (B == D or intersectible(schema, B, D)):
            continue

        if CONSIDER_NO_DUPLICATE_RELATIONSHIP:
            # R(i) - E(i+1) - R(i+2) and R - E' - R
            if i == m - l - 2 and P[i] == P[m - l - 2] and is_rel(P[i]) and is_binary(P[i]) and len(D) == 3 and \
                            D[1] != P[i + 1]:
                continue
            if i == m - l - 1 and len(D) == 4:
                if D[0] == D[2] and D[1] != D[3] and is_rel(D[0]) and is_binary(D[0]):
                    continue
                if D[1] == D[3] and D[0] != D[2] and is_rel(D[1]) and is_binary(D[1]):
                    continue

        # Does other path avoid P and Q?
        P_prime = join(P[:i + 1 - (llrsp_AD - 1)], rev_Q[j + (llrsp_AD - 1):])
        if len(P_prime) < len(P) and P[:len(P_prime)] == P_prime:
            continue

        Q_prime = join(P[i:][::-1], rev_Q[:j + 1][::-1])
        if len(Q_prime) < len(Q) and Q[:len(Q_prime)] == Q_prime:
            continue

        yield join(A[::-1], C), P_prime


def counterexample():
    schema = Schema()
    schema.addEntity("E1")
    schema.addEntity("E2")
    schema.addEntity("E3")
    schema.addEntity("E4")
    schema.addRelationship("R1", ("E1", Schema.ONE), ("E2", Schema.ONE))
    schema.addRelationship("R2", ("E2", Schema.ONE), ("E3", Schema.ONE))
    schema.addRelationship("R3", ("E2", Schema.ONE), ("E3", Schema.ONE))
    schema.addRelationship("R4", ("E2", Schema.ONE), ("E4", Schema.ONE))
    schema.addAttribute("R1", "X")
    schema.addAttribute("R2", "Y")
    schema.addAttribute("E2", "Z")

    d1 = RelationalDependency(RelationalVariable(["R2", "E2", "R1"], "X"), RelationalVariable(["R2"], "Y"))
    d2 = RelationalDependency(RelationalVariable(["R2", "E3", "R3", "E2"], "Z"), RelationalVariable(["R2"], "Y"))
    d3 = RelationalDependency(RelationalVariable(["R1", "E2", "R2", "E3", "R3", "E2"], "Z"),
                              RelationalVariable(["R1"], "X"))
    model = Model(schema, [d1, d2, d3])
    return schema, model
