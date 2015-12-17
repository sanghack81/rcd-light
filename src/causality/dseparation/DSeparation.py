import collections
import random

import networkx as nx
from causality.model import RelationalValidity
from causality.dseparation.AbstractGroundGraph import AbstractGroundGraph
from causality.model import ParserUtil

class DSeparation(object):

    def __init__(self, model):
        self.model = model
        self.perspectiveHopThresholdToAgg = {}
        self.ugs = {}

    def dSeparated(self, hopThreshold, relVar1Strs, relVar2Strs, condRelVarStrs,
                   relationalVariableSetChecker=RelationalValidity.checkValidityOfRelationalVariableSet):
        """
        relVar1Strs, relVar2Strs, and condRelVarStrs are sequences of parseable RelationalVariable strings
        Method checks if, in model, are relVars1 and relVars2 d-separated? Constructs the abstract ground graph (AGG) for
        the model, and checks to see if all paths are d-separated.
        """
        if not isinstance(relVar1Strs, collections.Iterable) or not relVar1Strs:
            raise Exception("relVars1 must be a non-empty sequence of parseable RelationalVariable strings")
        relVars1 = {ParserUtil.parseRelVar(relVarStr) for relVarStr in relVar1Strs}

        if not isinstance(relVar2Strs, collections.Iterable) or not relVar2Strs:
            raise Exception("relVars2 must be a non-empty sequence of parseable RelationalVariable strings")
        relVars2 = {ParserUtil.parseRelVar(relVarStr) for relVarStr in relVar2Strs}

        if not isinstance(condRelVarStrs, collections.Iterable):
            raise Exception("condRelVars must be a sequence of parseable RelationalVariable strings")
        condRelVars = {ParserUtil.parseRelVar(condRelVar) for condRelVar in condRelVarStrs}

        # check consistency of all three relational variable sets (perspectives, hop threshold, against schema)
        relationalVariableSetChecker(self.model.schema, hopThreshold, relVars1 | relVars2 | condRelVars)

        perspective = list(relVars1)[0].getBaseItemName()
        if (perspective, hopThreshold) not in self.perspectiveHopThresholdToAgg:
            agg = AbstractGroundGraph(self.model, perspective, hopThreshold)
            ug = agg2ug(agg)
            self.perspectiveHopThresholdToAgg[(perspective, hopThreshold)] = agg
            self.ugs[(perspective, hopThreshold)] = ug
        else:
            agg = self.perspectiveHopThresholdToAgg[(perspective, hopThreshold)]
            ug = self.ugs[(perspective, hopThreshold)]

        # expand relVars1, relVars2, condRelVars with all intersection variables they subsume
        relVars1 = {relVar for relVar1 in relVars1 for relVar in agg.getSubsumedVariables(relVar1)}
        relVars2 = {relVar for relVar2 in relVars2 for relVar in agg.getSubsumedVariables(relVar2)}
        condRelVars = {relVar for condRelVar in condRelVars for relVar in agg.getSubsumedVariables(condRelVar)}

        relVars1 -= condRelVars
        relVars2 -= condRelVars

        if relVars1 & relVars2 != set():
            return False

        if not relVars1 or not relVars2:
            return True

        return bfsReachability(relVars1, relVars2, condRelVars, agg, ug)


def agg2ug(agg):
    undirectedAGG = nx.DiGraph()
    undirectedAGG.add_nodes_from(agg.nodes())
    for (aggNode1, aggNode2) in agg.edges_iter():
        undirectedAGG.add_edge(aggNode1, aggNode2)
        undirectedAGG.add_edge(aggNode2, aggNode1)

    # (i) Add node s and add edge from s to all nodes in sourceNodes (X)
    # Label those links with a 1, those nodes as reachable, and all other nodes as not reached
    undirectedAGG.add_node('source', reach=True)
    return undirectedAGG



# shlee fix for performance (up to 5x)
def bfsReachability(relVars1, relVars2, condRelVars, agg, ug):
    determined = condRelVars
    descendant = {}
    for condRelVar in condRelVars:
        descendant[condRelVar] = True
        for ancestor in agg.getAncestors(condRelVar):
            descendant[ancestor] = True

    labeled = collections.defaultdict(set)
    total_label = set()
    for node in relVars1:
        ug.add_edge('source', node)
        labeled[1].add(('source', node))
        total_label.add(('source', node))

    iteration = 1

    keepGoing = True
    while keepGoing:
        keepGoing = False
        for (f, t) in labeled[iteration]:
            # for z in (nb for nb in ug[t] if f != nb and (t, nb) not in total_label):
            for z in ug[t]:
                if f != z and (t, z) not in total_label:
                    legal = False
                    if f in agg and t in agg[f] and z in agg and t in agg[z]:
                        if t in descendant:
                            legal = True
                    else:
                        if t not in determined:
                            legal = True
                    if legal:
                        if z in relVars2:
                            [ug.remove_edge('source', node) for node in relVars1]
                            return False
                        labeled[iteration + 1].add((t, z))
                        total_label.add((t, z))
                        keepGoing = True

        iteration += 1

    [ug.remove_edge('source', node) for node in relVars1]
    return True
