import collections
from causality.model import ParserUtil

def precision(trueValues, learnedValues):
    trueValueSet = set(trueValues)
    learnedValueSet = set(learnedValues)
    if not learnedValueSet:
        return 1.0
    else:
        return len(learnedValueSet & trueValueSet) / len(learnedValueSet)


def recall(trueValues, learnedValues):
    trueValueSet = set(trueValues)
    learnedValueSet = set(learnedValues)
    if not trueValueSet:
        return 1.0
    else:
        return len(learnedValueSet & trueValueSet) / len(trueValueSet)


def skeletonPrecision(model, learnedDependencies):
    checkInput(learnedDependencies)
    # Only counting edges (ignoring orientation), so add all reverses in true and learned and take the set
    learnedDependencies = [ParserUtil.parseRelDep(relDepStr) for relDepStr in learnedDependencies]
    learnedUndirectedDependencies = learnedDependencies + [dependency.reverse() for dependency in learnedDependencies]
    trueUndirectedDependencies = model.dependencies + [dependency.reverse() for dependency in model.dependencies]
    return precision(trueUndirectedDependencies, learnedUndirectedDependencies)


def skeletonRecall(model, learnedDependencies):
    checkInput(learnedDependencies)
    # Only counting edges (ignoring orientation), so add all reverses in true and learned and take the set
    learnedDependencies = [ParserUtil.parseRelDep(relDepStr) for relDepStr in learnedDependencies]
    learnedUndirectedDependencies = learnedDependencies + [dependency.reverse() for dependency in learnedDependencies]
    trueUndirectedDependencies = model.dependencies + [dependency.reverse() for dependency in model.dependencies]
    return recall(trueUndirectedDependencies, learnedUndirectedDependencies)


def orientedPrecision(model, learnedDependencies):
    checkInput(learnedDependencies)
    # Only counting oriented edges (ignoring unoriented), so remove dependencies that include their reverses
    learnedDependencies = {ParserUtil.parseRelDep(relDepStr) for relDepStr in learnedDependencies}
    learnedOrientedDependencies = set()
    for learnedDependency in learnedDependencies:
        if learnedDependency.reverse() not in learnedDependencies:
            learnedOrientedDependencies.add(learnedDependency)
    return precision(model.dependencies, learnedOrientedDependencies)


def orientedRecall(model, learnedDependencies):
    checkInput(learnedDependencies)
    # Only counting oriented edges (ignoring unoriented), so remove dependencies that include their reverses
    learnedDependencies = {ParserUtil.parseRelDep(relDepStr) for relDepStr in learnedDependencies}
    learnedOrientedDependencies = set()
    for learnedDependency in learnedDependencies:
        if learnedDependency.reverse() not in learnedDependencies:
            learnedOrientedDependencies.add(learnedDependency)
    return recall(model.dependencies, learnedOrientedDependencies)


def checkInput(learnedDependencies):
    if not isinstance(learnedDependencies, collections.Iterable) or isinstance(learnedDependencies, str):
        raise Exception("learnedDependencies must be a list of RelationalDependencies "
                        "or parseable RelationalDependency strings")