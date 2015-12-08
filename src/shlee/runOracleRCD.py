import logging

from causality.citest.CITest import Oracle
from causality.learning import ModelEvaluation
from causality.learning.RCD import RCD
from causality.modelspace import ModelGenerator
from causality.modelspace import SchemaGenerator
from shlee.RCDLight import RCDLight

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

# Parameters
numEntities = 3
numRelationships = 2
numDependencies = 10
hopThreshold = 4
maxNumParents = rcdDepth = 3

print(numEntities, numRelationships, numDependencies, hopThreshold, maxNumParents)
for i in range(1000):

    # Parameters
    schema = SchemaGenerator.generateSchema(numEntities, numRelationships, allowCycles=True, oneRelationshipPerPair=True)
    logger.info(schema)
    try:
        model = ModelGenerator.generateModel(schema, hopThreshold, numDependencies, maxNumParents=maxNumParents)
    except Exception:
        continue

    logger.info('Model: %s', model.dependencies)
    oracle = Oracle(model, 2 * hopThreshold)
    print('============= {} ============='.format(i))
    rcdl = RCDLight(schema, oracle, hopThreshold, depth=rcdDepth)
    rcdl.identifyUndirectedDependencies()
    rcdl.orientDependencies(truth=model.dependencies)
    # # Run RCD algorithm and collect statistics on learned model
    # rcd = RCD(schema, oracle, hopThreshold, depth=rcdDepth)
    # rcd.identifyUndirectedDependencies()
    # rcd.orientDependencies()

    # print(ModelEvaluation.skeletonPrecision(model, rcdl.undirectedDependencies))
    # print(ModelEvaluation.skeletonRecall(model, rcdl.undirectedDependencies))
    # for d in rcdl.orientedDependencies:
    #         print('{} --> {}'.format(d.relVar1, d.relVar2))
    # if ModelEvaluation.orientedPrecision(model, rcdl.orientedDependencies) != 1.0:
    #     print(schema)
    #     for d in model.dependencies:
    #         print('{} --> {}'.format(d.relVar1, d.relVar2))
    #
    print('Skeleton precision: %s', ModelEvaluation.skeletonPrecision(model, rcdl.undirectedDependencies))
    print('Skeleton recall: %s', ModelEvaluation.skeletonRecall(model, rcdl.undirectedDependencies))
    print('Oriented precision: %s', ModelEvaluation.orientedPrecision(model, rcdl.orientedDependencies))
    print('Oriented recall: %s', ModelEvaluation.orientedRecall(model, rcdl.orientedDependencies))

    # if ModelEvaluation.orientedRecall(model, rcd.orientedDependencies) != ModelEvaluation.orientedRecall(model, rcdl.orientedDependencies):
    #     print(ModelEvaluation.orientedRecall(model, rcd.orientedDependencies), ModelEvaluation.orientedRecall(model, rcdl.orientedDependencies))
    #     print(schema)
    #     print(model.dependencies)

    # print(rcd.report()[0]['Phase I'], rcd.report()[0]['Phase II'], rcdl.report()[0]['Phase I'],
    #       rcdl.report()[0]['Phase II'])
