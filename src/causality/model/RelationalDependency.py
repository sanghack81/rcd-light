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


from causality.model.Schema import SchemaItem

class RelationalVariable(object):

    def __init__(self, relPath, attrName):
        """
        relPath: an alternating sequence of entity and relationship names
        attrName
        NB: When used to represent attributes to generate, the first item is always the schema item
            on which the attribute exists
        """
        self.path = relPath
        self.attrName = attrName
        self.__h = 0
        self.__k = None


    def __key(self):
        if self.__k is None:
            self.__k = tuple(self.path), self.attrName
        return self.__k


    def __eq__(self, other):
        return isinstance(other, RelationalVariable) and self.__key() == other.__key()


    def __hash__(self):
        if self.__h == 0:
            self.__h = hash(self.__key())
        return self.__h


    def __lt__(self, other):
        if not isinstance(other, RelationalVariable) and not isinstance(other, RelationalVariableIntersection):
            raise TypeError("unorderable types: RelationalVariable() < {}()".format(type(other)))
        if isinstance(other, RelationalVariable):
            return self.__key() < other.__key()
        if isinstance(other, RelationalVariableIntersection):
            return self.__key() < other._RelationalVariableIntersection__key()


    def __repr__(self):
        return "{}.{}".format(str(self.path).replace("'", ""), self.attrName)


    def getBaseItemName(self):
        return self.path[0]


    def getTerminalItemName(self):
        return self.path[-1]


    def isExistence(self):
        return self.attrName == SchemaItem.EXISTS_ATTR_NAME


    def intersects(self, other):
        return self.getBaseItemName() == other.getBaseItemName() \
            and self.getTerminalItemName() == other.getTerminalItemName() \
            and self.attrName == other.attrName \
            and any([item1 != item2 for item1, item2 in zip(self.path, other.path)])


class RelationalDependency(object):

    def __init__(self, relVar1, relVar2):
        if not isinstance(relVar1, RelationalVariable) or not isinstance(relVar2, RelationalVariable):
            raise Exception("RelationalDependency expects two RelationalVariable objects")

        self.relVar1 = relVar1
        self.relVar2 = relVar2


    def __key(self):
        return self.relVar1._RelationalVariable__key(), self.relVar2._RelationalVariable__key()


    def __eq__(self, other):
        return isinstance(other, RelationalDependency) and self.__key() == other.__key()


    def __hash__(self):
        return hash(self.__key())


    def __lt__(self, other):
        if not isinstance(other, RelationalDependency):
            raise TypeError("unorderable types: RelationalDependency() < {}()".format(type(other)))
        return self.__key() < other.__key()


    def __repr__(self):
        return "{} -> {}".format(self.relVar1, self.relVar2)


    def reverse(self):
        newRelVar1Path = self.relVar1.path[:]
        newRelVar1Path.reverse()
        newRelVar2Path = [self.relVar1.getTerminalItemName()]
        newRelVar1AttrName = self.relVar2.attrName
        newRelVar2AttrName = self.relVar1.attrName
        return RelationalDependency(RelationalVariable(newRelVar1Path, newRelVar1AttrName),
                                    RelationalVariable(newRelVar2Path, newRelVar2AttrName))


class RelationalVariableIntersection(object):

    def __init__(self, relVar1, relVar2):
        if not isinstance(relVar1, RelationalVariable) or not isinstance(relVar2, RelationalVariable):
            raise Exception("RelationalVariableIntersection expects two RelationalVariable objects")

        self.relVar1 = relVar1
        self.relVar2 = relVar2
        self.__h = 0
        self.__k = None


    def __key(self):
        if self.__k is None:
            self.__k = self.relVar1._RelationalVariable__key() + self.relVar2._RelationalVariable__key() \
                if self.relVar1 < self.relVar2 \
                else self.relVar2._RelationalVariable__key() + self.relVar1._RelationalVariable__key()
        return self.__k


    def __eq__(self, other):
        return isinstance(other, RelationalVariableIntersection) and self.__key() == other.__key()

    def __hash__(self):
        if self.__h == 0:
            self.__h = hash(self.__key())
        return self.__h


    def __lt__(self, other):
        if not isinstance(other, RelationalVariableIntersection) and not isinstance(other, RelationalVariable):
            raise TypeError("unorderable types: RelationalVariableIntersection() < {}()".format(type(other)))
        if isinstance(other, RelationalVariableIntersection):
            return self.__key() < other.__key()
        if isinstance(other, RelationalVariable):
            return self.__key() < other._RelationalVariable__key()


    def __repr__(self):
        return "<{} {!r}, {!r}>".format(self.__class__.__name__, self.relVar1, self.relVar2)
