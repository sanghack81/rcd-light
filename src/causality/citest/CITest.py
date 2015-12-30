# Copyright (C) 2013, David Jensen for the Knowledge Discovery Laboratory
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
#
# Per article 5 of the Apache 2.0 License, some modifications to this code
# were made by the Sanghack Lee.
#
# Modifications Copyright (C) 2015 Sanghack Lee
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.



import collections
import functools
from causality.model.RelationalDependency import RelationalVariable
from causality.model.Aggregator import AverageAggregator
from causality.model.Aggregator import IdentityAggregator
from causality.model import ParserUtil
from causality.dseparation.DSeparation import DSeparation
import rpy2.robjects as robjects
r = robjects.r
import logging

logger = logging.getLogger(__name__)

class CITest(object):

    def isConditionallyIndependent(self, relVar1Str, relVar2Str, condRelVarStrs):
        raise NotImplementedError


class LinearCITest(CITest):

    def __init__(self, schema, dataStore, alpha=0.05, soeThreshold=0.01):
        self.schema = schema
        self.dataStore = dataStore
        self.alpha = alpha
        self.soeThreshold = soeThreshold


    def isConditionallyIndependent(self, relVar1Str, relVar2Str, condRelVarStrs):
        logger.debug("testing %s _||_ %s | { %s }", relVar1Str, relVar2Str, condRelVarStrs)
        if not isinstance(relVar1Str, str) and not isinstance(relVar1Str, RelationalVariable) or not relVar1Str:
            raise Exception("relVar1Str must be a parseable RelationalVariable string")
        if not isinstance(relVar2Str, str) and not isinstance(relVar2Str, RelationalVariable) or not relVar2Str:
            raise Exception("relVar2Str must be a parseable RelationalVariable string")
        if not isinstance(condRelVarStrs, collections.Iterable) or isinstance(condRelVarStrs, str):
            raise Exception("condRelVarStrs must be a sequence of parseable RelationalVariable strings")

        relVar1 = ParserUtil.parseRelVar(relVar1Str)
        relVar2 = ParserUtil.parseRelVar(relVar2Str)
        if len(relVar2.path) > 1:
            raise Exception("relVar2Str must have a singleton path")

        baseItemName = relVar1.getBaseItemName()
        relVarAggrs = [AverageAggregator(relVar1Str), IdentityAggregator(relVar2Str)]
        relVarAggrs.extend([AverageAggregator(condRelVarStr) for condRelVarStr in condRelVarStrs])

        relVar1Data = []
        relVar2Data = []
        condVarsData = []
        for i in range(len(condRelVarStrs)):
            condVarsData.append([])

        for idVal, row in self.dataStore.getValuesForRelVarAggrs(self.schema, baseItemName, relVarAggrs):
            if None in row:
                continue
            relVar1Data.append(float(row[0]))
            relVar2Data.append(float(row[1]))
            for i, value in enumerate(row[2:]):
                condVarsData[i].append(float(value))

        robjects.baseenv['treatment'] = robjects.FloatVector(relVar1Data)
        robjects.baseenv['outcome'] = robjects.FloatVector(relVar2Data)
        for i, condVarData in enumerate(condVarsData):
            robjects.baseenv['cond{}'.format(i)] = robjects.FloatVector(condVarData)

        if not condVarsData: # marginal
            linearModel = r.lm('outcome ~ treatment')
            effectSize = r('cor(treatment, outcome)^2')[0]
            summary = r.summary(linearModel)
        else:
            condVarIndexes = range(len(condVarsData))
            linearModel = r.lm('outcome ~ treatment + cond{}'.format(' + cond'.join(map(str, condVarIndexes))))
            effectSize = r('cor(residuals(lm(outcome ~ cond{condVarStrs})), '
                           'residuals(lm(treatment ~ cond{condVarStrs})))^2'.format(
                            condVarStrs=(' + cond'.join(map(str, condVarIndexes)))))[0]
            summary = r.summary(linearModel)

        pval =  summary.rx2('coefficients').rx(2,4)[0]
        logger.debug('soe: {}, pval: {}'.format(effectSize, pval))
        return pval > self.alpha or effectSize < self.soeThreshold


class Oracle(CITest):

    def __init__(self, model, hopThreshold=0):
        self.model = model
        self.hopThreshold = hopThreshold
        self.dsep = DSeparation(model)

    @functools.lru_cache(maxsize=10000)
    def isConditionallyIndependent(self, relVar1Str, relVar2Str, condRelVarStrs):
        return self.dsep.dSeparated(self.hopThreshold, [relVar1Str], [relVar2Str], condRelVarStrs)