import random

from causality.citest.CITest import Oracle
from causality.learning import ModelEvaluation
from causality.learning.RCD import RCD
from causality.model.Distribution import ConstantDistribution
from causality.modelspace import ModelGenerator
from causality.modelspace import SchemaGenerator, RelationalSpace
from shlee.RCDLight import RCDLight

while True:
    numEntities = random.randint(2, 3)
    numRelationships = random.randint(2, 3)
    numDependencies = random.randint(5, 10)
    hopThreshold = random.randint(2, 5)
    maxNumParents = rcdDepth = 4  # 4

    # Random Schema
    schema = SchemaGenerator.generateSchema(numEntities, numRelationships,
                                            entityAttrDistribution=ConstantDistribution(2),
                                            relationshipAttrDistribution=ConstantDistribution(1),
                                            allowCycles=True,
                                            oneRelationshipPerPair=False)
    # Random Model
    try:
        model = ModelGenerator.generateModel(schema, hopThreshold, numDependencies, maxNumParents=maxNumParents)
    except Exception:
        continue

    # Some RCD algorithm takes too much time.
    if len(RelationalSpace.getRelationalDependencies(schema, hopThreshold)) > 100:
        continue

    oracle = Oracle(model, 2 * hopThreshold)

    rcdl = RCDLight(schema, oracle, hopThreshold)
    rcdl.identifyUndirectedDependencies()
    rcdl.orientDependencies()

    rcd = RCD(schema, oracle, hopThreshold, depth=rcdDepth)
    rcd.identifyUndirectedDependencies()
    rcd.orientDependencies()

    assert ModelEvaluation.orientedPrecision(model, rcdl.orientedDependencies) == 1.0
    assert ModelEvaluation.skeletonPrecision(model, rcdl.undirectedDependencies) == 1.0
    assert ModelEvaluation.skeletonRecall(model, rcdl.undirectedDependencies) == 1.0
    rcdl_ori_recall = ModelEvaluation.orientedRecall(model, rcdl.orientedDependencies)
    rcd_ori_recall = ModelEvaluation.orientedRecall(model, rcd.orientedDependencies)
    assert rcdl_ori_recall >= rcd_ori_recall
    print('.', end='', flush=True)
    if rcdl_ori_recall > rcd_ori_recall:
        print('\nRCDL beats RCD:', rcdl_ori_recall, '>', rcd_ori_recall)
