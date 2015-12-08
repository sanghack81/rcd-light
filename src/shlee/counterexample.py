import logging

from causality.citest.CITest import Oracle
from causality.learning import ModelEvaluation
from causality.learning.RCD import RCD
import shlee.RCDLightNew

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

# Parameters

schema, model = shlee.RCDLightNew.counterexample()
logger.info('Model: %s', model.dependencies)
hopThreshold = max(len(d.relVar1.path) + 1 for d in model.dependencies)
oracle = Oracle(model, 2 * hopThreshold)

rcd = RCD(schema, oracle, hopThreshold, depth=2)
rcd.identifyUndirectedDependencies()
rcd.orientDependencies()
print('Skeleton precision:', ModelEvaluation.skeletonPrecision(model, rcd.undirectedDependencies))
print('Skeleton recall:', ModelEvaluation.skeletonRecall(model, rcd.undirectedDependencies))
precision = ModelEvaluation.orientedPrecision(model, rcd.orientedDependencies)
print('Oriented precision: %s', precision)
print('Oriented recall: %s', ModelEvaluation.orientedRecall(model, rcd.orientedDependencies))

rcdl = shlee.RCDLightNew.RCDLightNew(schema, oracle, hopThreshold, depth=2)
rcdl.identify_undirected_dependencies()
rcdl.orient_dependencies()
print('Skeleton precision:', ModelEvaluation.skeletonPrecision(model, rcdl.undirected_dependencies))
print('Skeleton recall:', ModelEvaluation.skeletonRecall(model, rcdl.undirected_dependencies))
precision = ModelEvaluation.orientedPrecision(model, rcdl.oriented_dependencies)
print('Oriented precision: %s', precision)
print('Oriented recall: %s', ModelEvaluation.orientedRecall(model, rcdl.oriented_dependencies))

assert ModelEvaluation.orientedRecall(model, rcdl.oriented_dependencies) > ModelEvaluation.orientedRecall(model,
                                                                                                          rcd.orientedDependencies)
