from causality.citest.CITest import Oracle
from causality.learning import ModelEvaluation
from causality.learning.RCD import RCD
from causality.modelspace import ModelGenerator
from causality.modelspace import SchemaGenerator
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Parameters
numEntities = 3
numRelationships = 2
numDependencies = 10
hopThreshold = 4
maxNumParents = rcdDepth = 3

# Parameters
schema = SchemaGenerator.generateSchema(numEntities, numRelationships, allowCycles=False, oneRelationshipPerPair=True)
logger.info(schema)
model = ModelGenerator.generateModel(schema, hopThreshold, numDependencies, maxNumParents=maxNumParents)
logger.info('Model: %s', model.dependencies)
oracle = Oracle(model, 2*hopThreshold)

# Run RCD algorithm and collect statistics on learned model
rcd = RCD(schema, oracle, hopThreshold, depth=rcdDepth)
rcd.identifyUndirectedDependencies()
rcd.orientDependencies()

logger.info('Skeleton precision: %s', ModelEvaluation.skeletonPrecision(model, rcd.undirectedDependencies))
logger.info('Skeleton recall: %s', ModelEvaluation.skeletonRecall(model, rcd.undirectedDependencies))
logger.info('Oriented precision: %s', ModelEvaluation.orientedPrecision(model, rcd.orientedDependencies))
logger.info('Oriented recall: %s', ModelEvaluation.orientedRecall(model, rcd.orientedDependencies))