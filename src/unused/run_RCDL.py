import logging
import random

from causality.citest.CITest import Oracle
from causality.learning import ModelEvaluation
from causality.model.Distribution import MarginalDistribution, ConstantDistribution
from causality.model.Schema import Schema
from causality.modelspace import ModelGenerator
from causality.modelspace import SchemaGenerator
from shlee.RCDLight import RCDLight

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)


class RandCard(MarginalDistribution):
    def sample(self, ignore):
        return Schema.ONE if random.random() < 0.5 else Schema.MANY


i = 0
while True:
    numEntities = random.randint(2, 3)
    numRelationships = random.randint(2, 2)
    numDependencies = random.randint(5, 12)
    hopThreshold = random.randint(2, 4)
    maxNumParents = rcdDepth = 5
    # print('setting', numEntities, numRelationships, numDependencies, hopThreshold, rcdDepth)

    # Parameters
    schema = SchemaGenerator.generateSchema(numEntities, numRelationships,
                                            entityAttrDistribution=ConstantDistribution(2),
                                            relationshipAttrDistribution=ConstantDistribution(1),
                                            allowCycles=True,
                                            oneRelationshipPerPair=False)
    logger.info(schema)
    try:
        model = ModelGenerator.generateModel(schema, hopThreshold, numDependencies, maxNumParents=maxNumParents)
    except Exception:
        continue

    i += 1

    oracle = Oracle(model, 2 * hopThreshold)
    # random background knowledge
    attr_orientation = [(dep.relVar1.attrName, dep.relVar2.attrName) for dep in model.dependencies]
    background_knowledge = random.sample(attr_orientation, random.randint(0, len(attr_orientation)))

    rcdl = RCDLight(schema, oracle, hopThreshold)
    rcdl.identifyUndirectedDependencies()
    rcdl.orientDependencies(background_knowledge if random.random() > 0.5 else None, attr_orientation)
    assert ModelEvaluation.skeletonPrecision(model, rcdl.undirectedDependencies) == 1.0
    assert ModelEvaluation.skeletonRecall(model, rcdl.undirectedDependencies) == 1.0

    if ModelEvaluation.orientedPrecision(model, rcdl.orientedDependencies) != 1.0:
        print('---------')
        print(attr_orientation)
        print(model.dependencies)
        assert ModelEvaluation.orientedPrecision(model, rcdl.orientedDependencies) == 1.0

    # to_print = [hopThreshold, rcdl.ci_record['num_poten'],
    #             rcdl.ci_record['Phase II'],
    #             rcdl.ci_record['num_rut'],
    #             c.seconds]
    print('.', end='', flush=True)
