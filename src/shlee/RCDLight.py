import collections
import itertools
import numbers
import logging

import networkx

from causality.dseparation import AbstractGroundGraph
from causality.model.RelationalDependency import RelationalVariable, RelationalDependency
from causality.modelspace import RelationalSpace

logger = logging.getLogger(__name__)


class SchemaDependencyWrapper:
    def __init__(self, schema, dependencies):
        self.schema = schema
        self.dependencies = dependencies


class RCDLight(object):
    '''
    RCD-Light (Lee and Honavar), directly modified from RCD by Maier et al.
    '''

    def __init__(self, schema, citest, hopThreshold, depth=None):
        if not isinstance(hopThreshold, numbers.Integral) or hopThreshold < 0:
            raise Exception("Hop threshold must be a non-negative integer: found {}".format(hopThreshold))
        if depth is not None and (not isinstance(depth, numbers.Integral) or depth < 0):
            raise Exception("Depth must be a non-negative integer or None: found {}".format(depth))

        self.schema = schema
        self.citest = citest
        self.hopThreshold = hopThreshold
        self.depth = depth
        self.potentialDependencySorter = lambda l: l  # no sorting by default
        self.generateSepsetCombinations = itertools.combinations
        self.undirectedDependencies = None
        self.orientedDependencies = None
        self.ciTestCache = {}
        self.ciRecord = {'Phase I': 0, 'Phase II': 0, 'total': 0}
        self.resetEdgeOrientationUsage()
        # RCDL
        self.parents = None
        self.non_colliders = set()

    def identifyUndirectedDependencies(self):
        logger.info('Phase I: identifying undirected dependencies')
        potentialDeps = RelationalSpace.getRelationalDependencies(self.schema, self.hopThreshold,
                                                                  includeExistence=False)
        potentialDeps = self.potentialDependencySorter(potentialDeps)

        keyfunc = lambda d: d.relVar2
        self.parents = {k: set(g.relVar1 for g in gs) for k, gs in
                        itertools.groupby(sorted(potentialDeps, key=keyfunc), key=keyfunc)}

        # Keep track of separating sets
        self.sepsets = {}

        self.maxDepthReached = -1
        if self.depth is None:
            self.depth = max(len(v) for v in self.parents.values())

        logger.info("Number of potentialDeps %d", len(potentialDeps))
        remainingDeps = potentialDeps[:]
        # Check for independencies
        for conditioningSetSize in range(self.depth + 1):
            self.maxDepthReached = conditioningSetSize
            testedAtCurrentSize = False
            logger.info("Conditioning set size %d", conditioningSetSize)
            logger.debug("remaining dependencies %s", remainingDeps)
            for potentialDep in potentialDeps:
                logger.debug("potential dependency %s", potentialDep)
                if potentialDep not in remainingDeps:
                    continue
                relVar1, relVar2 = potentialDep.relVar1, potentialDep.relVar2
                sepset, curTestedAtCurrentSize = self.findSepset(relVar1, relVar2, conditioningSetSize,
                                                                 phaseForRecording='Phase I')
                testedAtCurrentSize = testedAtCurrentSize or curTestedAtCurrentSize
                if sepset is not None:
                    logger.debug("removing edge %s -- %s", relVar1, relVar2)
                    self.sepsets[relVar1, relVar2] = set(sepset)
                    self.sepsets[relVar2, relVar1] = set(sepset)
                    remainingDeps.remove(potentialDep)
                    potentialDepReverse = potentialDep.reverse()
                    remainingDeps.remove(potentialDepReverse)
                    self.removeDependency(potentialDep)
            if not testedAtCurrentSize:  # exit early, no possible sepsets of a larger size
                break
            potentialDeps = remainingDeps[:]

        self.undirectedDependencies = remainingDeps
        logger.info("Undirected dependencies: %s", self.undirectedDependencies)
        logger.info(self.ciRecord)

    def findSepset(self, relVar1, relVar2, conditioningSetSize, phaseI=True, phaseForRecording='Phase I'):
        assert len(relVar2.path) == 1
        neighbors2 = set(self.parents[relVar2])
        logger.debug("neighbors2 %s", neighbors2)
        if relVar1 in neighbors2:
            neighbors2.remove(relVar1)
        testedAtCurrentSize = False
        if conditioningSetSize <= len(neighbors2):
            for candidateSepSet in self.generateSepsetCombinations(neighbors2, conditioningSetSize):
                logger.debug("checking %s _||_ %s | { %s }", relVar1, relVar2, candidateSepSet)
                testedAtCurrentSize = True
                ciTestKey = (relVar1, relVar2, tuple(sorted(list(candidateSepSet))))
                if ciTestKey not in self.ciTestCache:
                    self.ciRecord[phaseForRecording] += 1
                    depthStr = 'depth {}'.format(len(candidateSepSet))
                    if phaseI:
                        self.ciRecord.setdefault(depthStr, 0)
                        self.ciRecord[depthStr] += 1
                    self.ciRecord['total'] += 1
                    isCondInd = self.citest.isConditionallyIndependent(relVar1, relVar2, candidateSepSet)
                    self.ciTestCache[ciTestKey] = isCondInd
                else:
                    logger.debug("found result in CI cache")
                if self.ciTestCache[ciTestKey]:
                    return set(candidateSepSet), testedAtCurrentSize
        return None, testedAtCurrentSize

    def removeDependency(self, dependency: RelationalDependency):
        depReverse = dependency.reverse()
        self.parents[dependency.relVar2].remove(dependency.relVar1)
        self.parents[depReverse.relVar2].remove(depReverse.relVar1)

    def orientDependencies(self, background_knowledge=None, truth=None):
        logger.info('Phase II: orienting dependencies')
        if not hasattr(self, 'undirectedDependencies') or self.undirectedDependencies is None:
            raise Exception("No undirected dependencies found. Try running Phase I first.")
        if not hasattr(self, 'sepsets') or self.sepsets is None:
            raise Exception("No sepsets found. Try running Phase I first.")

        if self.depth is None:
            self.depth = max(len(v) for v in self.parents.values())

        self.applyOrientationRules(background_knowledge, truth=truth)

        self.orientedDependencies = set()
        for effect, causes in self.parents.items():
            for cause in causes:
                dep = RelationalDependency(cause, effect)
                rev = dep.reverse()
                if rev.relVar1 not in self.parents[rev.relVar2]:
                    self.orientedDependencies.add(dep)

        logger.info("Separating sets: %s", self.sepsets)
        logger.info("Oriented dependencies: %s", self.orientedDependencies)
        logger.info(self.ciRecord)
        logger.info(self.edgeOrientationRuleFrequency)

    def applyOrientationRules(self, background_knowledge, truth=None):
        self.applyColliderDetectionAndRBO(truth=truth)
        self.applySepsetFreeOrientationRules(background_knowledge)

    def applySepsetFreeOrientationRules(self, background_knowledge):
        newOrientationsFound = True
        # PDAG where an undirected edge is represented as two directed edges between two attribute classes
        CDG = networkx.DiGraph()
        for effect, causes in self.parents.items():
            for cause in causes:
                CDG.add_edge(cause.attrName, effect.attrName)

        is_oriented_as = lambda x, y: CDG.has_edge(x, y) and not CDG.has_edge(y, x)
        is_unoriented = lambda x, y: CDG.has_edge(x, y) and CDG.has_edge(y, x)
        orient = lambda x, y: CDG.remove_edge(y, x) if CDG.has_edge(y, x) else None
        succ = lambda x: set(CDG.successors(x))
        pred = lambda x: set(CDG.predecessors(x))

        if background_knowledge is not None:
            for x, y in background_knowledge:
                assert CDG.has_edge(x, y)
                orient(x, y)

        while newOrientationsFound:
            newOrientationsFound = False
            for y, (x, z) in list(self.non_colliders):
                if not is_unoriented(y, x) and not is_unoriented(y, z):
                    self.non_colliders.remove((y, frozenset({x, z})))
                    continue

                # R1: KNC
                if is_oriented_as(x, y) and is_unoriented(y, z):
                    orient(y, z)
                    self.recordEdgeOrientationUsage('KNC')
                    newOrientationsFound = True
                    self.non_colliders.remove((y, frozenset({x, z})))
                    break
                elif is_oriented_as(z, y) and is_unoriented(y, x):
                    orient(y, x)
                    self.recordEdgeOrientationUsage('KNC')
                    newOrientationsFound = True
                    self.non_colliders.remove((y, frozenset({x, z})))
                    break

                # R3: MR3, x --> w <-- z
                for w in succ(x) & succ(y) & succ(z):

                    if is_oriented_as(x, w) and is_oriented_as(z, w) and is_unoriented(y, w):
                        orient(y, w)
                        self.recordEdgeOrientationUsage('MR3')
                        newOrientationsFound = True

                # R4: MR4, # r --> b --> l
                for l, t, r in ((x, y, z), (z, y, x)):
                    if is_unoriented(t, l):
                        for b in succ(r):
                            if is_oriented_as(r, b) and is_oriented_as(b, l):
                                orient(t, l)
                                self.recordEdgeOrientationUsage('MR4')
                                newOrientationsFound = True
            # R2:
            for v1 in CDG.nodes_iter():
                for v2 in succ(v1) - pred(v1):
                    for v3 in succ(v2) - pred(v2):
                        assert v1 != v3
                        if is_unoriented(v1, v3):
                            orient(v1, v3)
                            self.recordEdgeOrientationUsage('CA')
                            newOrientationsFound = True

        for effect, causes in self.parents.items():
            for cause in list(causes):
                if is_oriented_as(effect.attrName, cause.attrName):
                    causes.remove(cause)  # remove if oriented in an opposite direction

    def _findUnshieldedTriples(self):
        done = set()
        data = sorted(self.undirectedDependencies, key=lambda d: d.relVar2.attrName)
        depsPerAttrName = collections.defaultdict(set, {k: set(g) for k, g in
                                                        itertools.groupby(data, key=lambda d: d.relVar2.attrName)})

        extender = AbstractGroundGraph.extendPath
        for d_yx in self.undirectedDependencies:
            Qy = d_yx.relVar1
            for d_zy in depsPerAttrName[Qy.attrName]:
                Rz = d_zy.relVar1
                for QR in sorted(extender(self.schema, d_yx.relVar1.path, d_zy.relVar1.path),
                                 key=lambda p: len(p)):
                    QRz = RelationalVariable(QR, Rz.attrName)
                    if QRz != d_yx.relVar2 and QRz not in self.parents[d_yx.relVar2]:
                        if (QRz, Qy, d_yx.relVar2) not in done:
                            yield QRz, Qy, d_yx.relVar2, d_zy, d_yx
                            done.add((QRz, Qy, d_yx.relVar2))

    def applyColliderDetectionAndRBO(self, truth=None):
        true_order = {(d.relVar1.attrName, d.relVar2.attrName) for d in truth} if truth is not None else None

        newOrientationsFound = False
        oriented_pairs = set()
        orientations_cd = set()
        orientations_rbo = set()

        for rv1, rv2, rv3, d12, d23 in sorted(self._findUnshieldedTriples(),
                                              key=lambda x: (
                                                          len(x[0].path) > self.hopThreshold + 1, len(self.parents[x[2]]))):
            z, y, x = rv1.attrName, rv2.attrName, rv3.attrName
            if {frozenset({z, y}), frozenset({x, y})} <= oriented_pairs:  # if both are oriented
                continue
            sepset = self.findRecordAndReturnSepset(rv1, rv3)
            if sepset is not None:
                # TODO
                if rv2 not in sepset:  # collider
                    oriented_pairs |= {frozenset({z, y}), frozenset({x, y})}
                    orientations_cd |= {(z, y), (x, y)}
                    self.recordEdgeOrientationUsage('CD')
                    newOrientationsFound = True
                elif x == z:  # non-collider, RBO
                    oriented_pairs.add(frozenset({y, x}))
                    orientations_rbo.add((y, x))
                    self.recordEdgeOrientationUsage('RBO')
                    newOrientationsFound = True
                else:
                    self.non_colliders.add((y, frozenset({x, z})))
                if true_order is not None:
                    if orientations_cd <= true_order and orientations_rbo <= true_order:
                        pass
                    else:
                        print('wrong triple: {} -- {} -- {} based on {} and {}'.format(rv1, rv2, rv3, d12, d23))

        # self contradictory?
        oris = orientations_cd | orientations_rbo
        if oris & {(y, x) for x, y in oris}:
            print('conflicted: {} -- {}'.format(x, y))

        for effect, causes in self.parents.items():
            for cause in list(causes):
                if (effect.attrName, cause.attrName) in oris:
                    causes.remove(cause)  # remove if oriented in an opposite direction

        return newOrientationsFound

    def findRecordAndReturnSepset(self, relVar1, relVar2):
        if (relVar1, relVar2) in self.sepsets:
            return self.sepsets[(relVar1, relVar2)]
        else:
            sepset = None
            logger.debug("findRecordAndReturnSepset for %s and %s", relVar1, relVar2)
            for conditioningSetSize in range(self.depth + 1):
                sepset, testedAtCurrentSize = self.findSepset(relVar1, relVar2, conditioningSetSize,
                                                              phaseI=False, phaseForRecording='Phase II')
                if sepset is not None:
                    logger.debug("recording sepset %s", sepset)
                    self.sepsets[(relVar1, relVar2)] = sepset
                    self.sepsets[(relVar2, relVar1)] = sepset
                    break
                if not testedAtCurrentSize:  # exit early, no other candidate sepsets to check
                    break
            return sepset

    def recordEdgeOrientationUsage(self, edgeOrientationName):
        self.edgeOrientationRuleFrequency[edgeOrientationName] += 1

    def resetEdgeOrientationUsage(self):
        self.edgeOrientationRuleFrequency = {'CD': 0, 'KNC': 0, 'CA': 0, 'MR3': 0, 'RBO': 0, 'MR4': 0}

    def report(self):
        return self.ciRecord, self.edgeOrientationRuleFrequency


def runRCDLight(schema, citest, hopThreshold, depth=None):
    rcd = RCDLight(schema, citest, hopThreshold, depth)
    rcd.identifyUndirectedDependencies()
    rcd.orientDependencies()
    return rcd.orientedDependencies
