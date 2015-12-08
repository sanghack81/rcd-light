from causality.model import ParserUtil
from causality.model.Model import Model
from causality.modelspace import RelationalSpace
import random

def generateModel(schema, hopThreshold, numDependencies, maxNumParents=None, dependencies=None, randomPicker=random.sample):
    """
    dependencies is an optional set of potential dependencies that the model chooses its dependencies from.
    If dependencies=None, then the potential dependencies is the full space given by the schema and hopThreshold.
    If dependencies is specified, then hopThreshold is ignored.
    dependencies is only for testing so consistency with schema isn't checked.
    dependencies will be modified in place as they get selected without replacement.
    """
    if not dependencies:
        dependencies = RelationalSpace.getRelationalDependencies(schema, hopThreshold)
    else:
        dependencies = [ParserUtil.parseRelDep(relDepStr) for relDepStr in dependencies]
    if len(dependencies) < numDependencies:
        raise Exception("Could not generate a model: not enough dependencies to draw from")

    if not numDependencies:
        return Model(schema, [])

    attrToNumParents = {}

    modelDeps = []
    model = None
    while len(dependencies) > 0 and len(modelDeps) < numDependencies:
        dependency = randomPicker(dependencies, 1)[0]
        dependencies.remove(dependency)
        modelDeps.append(dependency)
        try:
            model = Model(schema, modelDeps)
            attrToNumParents.setdefault(dependency.relVar2, 0)
            attrToNumParents[dependency.relVar2] += 1
            if maxNumParents and attrToNumParents[dependency.relVar2] > maxNumParents:
                raise Exception
        except Exception:
            model = None
            modelDeps.remove(dependency)

    if not model or len(model.dependencies) < numDependencies:
        raise Exception("Could not generate a model: failed to find a model with {} dependenc[y|ies]".format(numDependencies))

    return model