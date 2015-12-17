import datetime
import logging
import random

from causality.citest.CITest import Oracle
from causality.learning import ModelEvaluation
from causality.learning.RCD import RCD
from causality.model.Distribution import MarginalDistribution, ConstantDistribution
from causality.model.Schema import Schema
from causality.modelspace import ModelGenerator
from causality.modelspace import SchemaGenerator
from shlee.RCDLight import RCDLight

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

numEntities = 3  # random.randint(2, 3)
numRelationships = 3  # random.randint(2, 2)
numDependencies = 3  # random.randint(5, 10)
hopThreshold = 3  # random.randint(2, 4)
maxNumParents = rcdDepth = 3  # 4


class RandCard(MarginalDistribution):
    def sample(self, ignore):
        return Schema.ONE if random.random() < 0.5 else Schema.MANY


print('setting', numEntities, numRelationships, numDependencies, hopThreshold, rcdDepth)
COMPARE = True
header = True
i = 0
while i < 100:
    # Parameters
    schema = SchemaGenerator.generateSchema(numEntities, numRelationships,
                                            entityAttrDistribution=ConstantDistribution(2),
                                            relationshipAttrDistribution=ConstantDistribution(1),
                                            cardinalityDistribution=RandCard(),
                                            allowCycles=True,
                                            oneRelationshipPerPair=True)
    logger.info(schema)
    try:
        model = ModelGenerator.generateModel(schema, hopThreshold, numDependencies, maxNumParents=maxNumParents)
    except Exception:
        continue

    i += 1

    oracle = Oracle(model, 2 * hopThreshold)
    if COMPARE:
        a = datetime.datetime.now()
        rcd = RCD(schema, oracle, hopThreshold, depth=rcdDepth)
        rcd.identifyUndirectedDependencies()
        rcd.orientDependencies()
        b = datetime.datetime.now()
        c = b - a

    rcdl = RCDLight(schema, oracle, hopThreshold, depth=rcdDepth)
    # rcdl = RCDLightNew(schema, oracle, hopThreshold, depth=rcdDepth)
    rcdl.identify_undirected_dependencies()
    assert ModelEvaluation.skeletonPrecision(model, rcdl.undirectedDependencies) == 1.0
    assert ModelEvaluation.skeletonRecall(model, rcdl.undirectedDependencies) == 1.0
    rcdl.orient_dependencies(old_mode=True, simultaneous=True)

    # rcdl2 = RCDLightNew(schema, oracle, hopThreshold, depth=rcdDepth)
    # rcdl2.identify_undirected_dependencies()
    # rcdl2.orient_dependencies(old_mode=True, simultaneous=True)

    if COMPARE:
        assert ModelEvaluation.orientedRecall(model, rcdl.orientedDependencies) >= ModelEvaluation.orientedRecall(
                model,
                rcd.orientedDependencies)
        # if ModelEvaluation.orientedRecall(model, rcdl.oriented_dependencies) > ModelEvaluation.orientedRecall(model,
        #                                                                                                       rcd.orientedDependencies):
        #     print('beat it!')
        #     print(schema)
        #     print(model.dependencies)
    assert ModelEvaluation.orientedPrecision(model, rcdl.orientedDependencies) == 1.0
    if COMPARE:
        if header:
            print('poten', 'rcdl_p2_ci', 'rcdl_num_rut', 'rcd_ut_searched', 'rcd_ut_found', 'rcd_ci_phase2',
                  'rcd_agg_V2', 'rcd_agg_E2', 'time')
            header = False
        # print(rcdl.ci_record['Phase I'], rcdl.ci_record['Phase II'], rcd.ciRecord['Phase I'], rcd.ciRecord['Phase II'], rcd.full_num_agg_nodes,
        #       rcd.full_num_agg_edges, rcd.after_num_agg_nodes, rcd.after_num_agg_edges)
        to_print = [rcdl.ciRecord['num_poten'],
                    rcdl.ciRecord['Phase II'],
                    rcdl.ciRecord['num_rut'],
                    rcd.utRecord['searched'],
                    rcd.utRecord['found'],
                    rcd.ciRecord['Phase II'],
                    rcd.after_num_agg_nodes,
                    rcd.after_num_agg_edges,
                    c.seconds]
        print(*to_print)
        # else:
        #     if header:
        #         print('rcdl_p1_ci', 'rcdl_p2_ci', 'rcdl2_p2_ci')
        #         header = False
        #     print(rcdl.ci_record['Phase I'], rcdl.ci_record['Phase II'], rcdl2.ci_record['Phase II'])
