import logging
import random

import datetime

from causality.citest.CITest import Oracle
from causality.learning import ModelEvaluation
from causality.learning.RCD import RCD
from causality.model.Distribution import MarginalDistribution, ConstantDistribution
from causality.model.Schema import Schema
from causality.modelspace import ModelGenerator
from causality.modelspace import SchemaGenerator
from shlee.RCDLightNew import RCDLightNew

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

numEntities = 3  # random.randint(2, 3)
numRelationships = 3  # random.randint(2, 2)
numDependencies = 10 # random.randint(5, 10)
hopThreshold = 4  # random.randint(2, 4)
maxNumParents = rcdDepth = 3  # 4


class RandCard(MarginalDistribution):
    def sample(self, ignore):
        return Schema.ONE if random.random() < 0.5 else Schema.MANY


print('setting',numEntities, numRelationships, numDependencies, hopThreshold, rcdDepth)
header = True
i = 0
while i < 50:
    # Parameters
    schema = SchemaGenerator.generateSchema(numEntities, numRelationships,entityAttrDistribution=ConstantDistribution(2),relationshipAttrDistribution=ConstantDistribution(1),
                                            allowCycles=True,
                                            oneRelationshipPerPair=False)
    logger.info(schema)
    try:
        model = ModelGenerator.generateModel(schema, hopThreshold, numDependencies, maxNumParents=maxNumParents)
    except Exception:
        continue

    i += 1

    oracle = Oracle(model, 2 * hopThreshold)


    a = datetime.datetime.now()
    rcdl = RCDLightNew(schema, oracle, hopThreshold, depth=rcdDepth)
    # rcdl = RCDLightNew(schema, oracle, hopThreshold, depth=rcdDepth)
    rcdl.identify_undirected_dependencies()
    assert ModelEvaluation.skeletonPrecision(model, rcdl.undirected_dependencies) == 1.0
    assert ModelEvaluation.skeletonRecall(model, rcdl.undirected_dependencies) == 1.0
    rcdl.orient_dependencies(old_mode=True, simultaneous=True)
    b = datetime.datetime.now()
    c = b-a

    if header:
        print('hopThreshold','poten','rcdl_p2_ci', 'rcdl_num_rut','time')
        header = False
    to_print = [hopThreshold,rcdl.ci_record['num_poten'],
        rcdl.ci_record['Phase II'],
        rcdl.ci_record['num_rut'],
        c.seconds]
    print(*to_print)
