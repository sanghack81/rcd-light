# Copyright 2015 Sanghack Lee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import logging

import shlee.RCDLight
import shlee.RCDLight
from causality.citest.CITest import Oracle
from causality.dseparation.AbstractGroundGraph import AbstractGroundGraph
from causality.learning import ModelEvaluation
from causality.learning.RCD import RCD, SchemaDependencyWrapper
from causality.model.RelationalDependency import RelationalVariable

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

# Parameters

schema, model = shlee.RCDLight.incompleteness_example()
logger.info('Model: %s', model.dependencies)
hopThreshold = max(len(d.relVar1.path) + 1 for d in model.dependencies)
oracle = Oracle(model, 3 * hopThreshold)

rcd = RCD(schema, oracle, hopThreshold, depth=2)
rcd.identifyUndirectedDependencies()
rcd.orientDependencies()
print('Skeleton precision:', ModelEvaluation.skeletonPrecision(model, rcd.undirectedDependencies))
print('Skeleton recall:', ModelEvaluation.skeletonRecall(model, rcd.undirectedDependencies))
precision = ModelEvaluation.orientedPrecision(model, rcd.orientedDependencies)
print('Oriented precision:', precision)
print('Oriented recall:', ModelEvaluation.orientedRecall(model, rcd.orientedDependencies))

rcdl = shlee.RCDLight.RCDLight(schema, oracle, hopThreshold)
rcdl.identifyUndirectedDependencies()
rcdl.orientDependencies()
print('Skeleton precision:', ModelEvaluation.skeletonPrecision(model, rcdl.undirectedDependencies))
print('Skeleton recall:', ModelEvaluation.skeletonRecall(model, rcdl.undirectedDependencies))
precision = ModelEvaluation.orientedPrecision(model, rcdl.orientedDependencies)
print('Oriented precision:', precision)
print('Oriented recall:', ModelEvaluation.orientedRecall(model, rcdl.orientedDependencies))

assert ModelEvaluation.orientedRecall(model, rcdl.orientedDependencies) == \
       ModelEvaluation.orientedRecall(model, rcd.orientedDependencies) == \
       0.0

# Demonstrate that there is no 'unshielded triple' in AGGs for the counter-example.
schema, model = shlee.RCDLight.incompleteness_example()
hopThreshold = max(len(d.relVar1.path) + 1 for d in model.dependencies)
oracle = Oracle(model, 3 * hopThreshold)

schemaDepWrapper = SchemaDependencyWrapper(schema, model.dependencies)
perspectives = [si.name for si in schema.getSchemaItems()]
perspectiveToAgg = {perspective: AbstractGroundGraph(schemaDepWrapper, perspective, 3 * hopThreshold)
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
                    assert False
# There is no 'unshielded triple' in AGGs
