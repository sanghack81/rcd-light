import logging

from causality.citest.CITest import Oracle
from causality.dseparation.AbstractGroundGraph import AbstractGroundGraph
from causality.learning import ModelEvaluation
from causality.learning.RCD import RCD, SchemaDependencyWrapper
import shlee.RCDLightNew
from causality.model.RelationalDependency import RelationalVariable

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

# Parameters

schema, model = shlee.RCDLightNew.counterexample()
logger.info('Model: %s', model.dependencies)
hopThreshold = max(len(d.relVar1.path) + 1 for d in model.dependencies)
oracle = Oracle(model, 3 * hopThreshold)

schemaDepWrapper = SchemaDependencyWrapper(schema, model.dependencies)
perspectives = [si.name for si in schema.getSchemaItems()]
perspectiveToAgg = {perspective: AbstractGroundGraph(schemaDepWrapper, perspective, 3*hopThreshold)
                              for perspective in perspectives}

for agg in perspectiveToAgg.values():
    for node1 in agg.nodes():
        neighbors1 = set(agg.predecessors(node1) + agg.successors(node1))
        for node2 in neighbors1:
            neighbors2 = set(agg.predecessors(node2) + agg.successors(node2)) - {node1}
            for node3 in neighbors2:
                if node3 not in neighbors1:
                    if not isinstance(node1, RelationalVariable) or not isinstance(node2, RelationalVariable) or \
                            not isinstance(node3, RelationalVariable):
                        continue
                    print(node1, node2, node3)

