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


import random

from causality.citest.CITest import Oracle
from causality.learning import ModelEvaluation
from causality.learning.RCD import RCD
from causality.model.Distribution import ConstantDistribution
from causality.modelspace import ModelGenerator
from causality.modelspace import SchemaGenerator, RelationalSpace
from shlee.RCDLight import RCDLight

# This generates random schemas and models, and compare their theoretical performance based on
# conditional independence tests from Abstract Ground Graphs (AGGs)
# One can see that Improved RCD-Light can identify more orientations than RCD.
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
    # This limits generated models to be 'easy'
    if len(RelationalSpace.getRelationalDependencies(schema, hopThreshold)) > 100:
        continue

    # This oracle uses AGGs.
    oracle = Oracle(model, 2 * hopThreshold)

    # Since CI-tests are cached, comparing time spent on RCD and RCDL directly should be avoided.
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
