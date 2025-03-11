# 
# Copyright 2025 Chair of EDA, Technical University of Munich
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#       http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import re

class MetaTraceModel_base:
    __isFrozen = False

    def __setattr__(self, key, value):
        if self.__isFrozen and not hasattr(self, key):
            raise TypeError("Attempting to add new attribute to frozen class %r" %self)
        object.__setattr__(self, key, value)

    def __init__(self):
        self.__isFrozen = True

class Trace(MetaTraceModel_base):

    def __init__(self, name_, core_):
        self.name = name_
        self.core = core_
        self.instructionGroups = []
        self.traceValues = {}
        self.separator = "|"
        
        super().__init__()

    def createAndAddTraceValue(self, name_, type_="int", size_=-1):
        trVal = TraceValue(name_, type_, size_)
        self.traceValues[name_] = trVal
        return trVal
        
    def createAndAddInstructionGroup(self, name_, id_):
        instrType = InstructionGroup(name_, id_, self)
        self.instructionGroups.append(instrType)
        return instrType

    def getAllTraceValues(self):
        return self.traceValues.values()

    def getAllInstructionGroups(self):
        return self.instructionGroups

    def getAllMappings(self):
        mappings = []
        for instrType_i in self.getAllInstructionGroups():
            mappings.extend(instrType_i.getAllMappings())
        return mappings

    def getAllDescriptions(self):
        descriptions = []
        for map_i in self.getAllMappings():
            descriptions.append(map_i.description)
        return descriptions

    def setSeparator(self, sep_):
        self.separator = sep_

    def getSeparator(self):
        return self.separator
    
class InstructionGroup(MetaTraceModel_base):

    def __init__(self, name_, id_, parent_):
        self.name = name_
        self.identifier = id_
        self.instructions = []
        self.bitfields = []
        self.mappings = {}
        self.__parent = parent_
        
        super().__init__()

    def addInstruction(self, name_):
        self.instructions.append(name_)

    def addBitfield(self, name_):
        self.bitfields.append(name_)

    def createAndAddMapping(self, trValName_, description_, position_):

        # Look up trace-value in dict. of parent/trace-model
        try:
            trVal = self.__parent.traceValues[trValName_]
        except KeyError:
            raise TypeError("Mapping for instruction %s: Cannot create mapping for trace-value %s. Trace-value does not exist (Make sure to add all trace-values to the trace-model before creating mappings)" %(self.name, trValName_))

        mapping = Mapping(self, trVal, description_, position_)
        self.mappings[trValName_] = mapping
        return mapping

    def getAllInstructions(self):
        return self.instructions
    
    def getAllBitfields(self):
        return self.bitfields
    
    def getAllMappings(self):
        return self.mappings.values()

    def getMapping(self, trVal_):
        try:
            return self.mappings[trVal_.name]
        except KeyError:
            return None
        
    def getAllPreMappings(self):
        mappings = []
        for map_i in self.mappings:
            map_i = self.mappings[map_i]
            if map_i.positionIsPre():
                mappings.append(map_i)
        return mappings

    def getAllPostMappings(self):
        mappings = []
        for map_i in self.mappings:
            map_i = self.mappings[map_i]
            if map_i.positionIsPost():
                mappings.append(map_i)
        return mappings

    
class TraceValue(MetaTraceModel_base):

    def __init__(self, name_, type_, size_):
        self.name = name_
        self.dataType = type_
        self.size = size_
        
        super().__init__()

class Mapping(MetaTraceModel_base):

    def __init__(self, type_, trVal_, descr_, pos_):
        self.instructionGroup = type_
        self.traceValue = trVal_
        # self.description = Description(self, descr_)
        self.description = DescriptionParser().parse_description_string(descr_, self.instructionGroup)
        if pos_ not in ["pre", "post"]:
            raise RuntimeError("Cannot create object of type MetaTraceModel::Mapping with position \"%s\"! Currently supported positions are \"pre\" and \"post\"" %pos_)
        self.position = pos_
        
        super().__init__()

    def positionIsPre(self):
        return (self.position == "pre")

    def positionIsPost(self):
        return (self.position == "post")
        
    def getTraceValue(self):
        return self.traceValue

    def getDescription(self):
        return self.description

    def getInstructionGroup(self):
        return self.instructionGroup

class Description(MetaTraceModel_base):
    def __init__(self, type_, value, resolved=False, nested_descriptions=None):
        self.type = type_
        self.value = value
        self.resolved = resolved
        self.nested_descriptions = nested_descriptions or []

    def getDescriptionType(self):
        return self.type

    def getDescriptionValue(self):
        return self.value
    
    def getNestedDescriptions(self):
        return self.nested_descriptions

    def __repr__(self):
        if self.nested_descriptions:
            nested_repr = ', '.join([repr(nd) for nd in self.nested_descriptions])
            return f"Description(type={self.type}, value={self.value}, resolved={self.resolved} , nested_descriptions=[{nested_repr}])"
        else:
            return f"Description(type={self.type}, value={self.value}, resolved={self.resolved})"

class DescriptionParser(MetaTraceModel_base):
    def parse_description_string(self, desc_string, instructionGroup, resolved = False):
        parsed_descriptions = []
        resolved = resolved
        buffer = ""
        i = 0

        while i < len(desc_string):
            if desc_string[i:i+3] == "$pc":
                if buffer:
                    parsed_descriptions.append(Description(type_="string", value=buffer, resolved=resolved))
                    buffer = ""
                parsed_descriptions.append(Description(type_="pc", value="pc", resolved=resolved))
                i += 3
            elif desc_string[i:i+4] == "$asm":
                if buffer:
                    parsed_descriptions.append(Description(type_="string", value=buffer, resolved=resolved))
                    buffer = ""
                parsed_descriptions.append(Description(type_="asm", value="asm", resolved=resolved))
                i += 4
            elif desc_string[i:i+5] == "$code":
                if buffer:
                    parsed_descriptions.append(Description(type_="string", value=buffer, resolved=resolved))
                    buffer = ""
                parsed_descriptions.append(Description(type_="code", value="code", resolved=resolved))
                i += 5
            elif desc_string[i:i+5] == "$reg{":
                if buffer:
                    parsed_descriptions.append(Description(type_="string", value=buffer, resolved=resolved))
                    buffer = ""
                i += 5
                nested_content, i = self.extract_nested_content(desc_string, i)
                parsed_descriptions.append(Description(type_="reg", value="reg", resolved=resolved, nested_descriptions=self.parse_description_string(nested_content, instructionGroup, resolved=resolved)))
            elif desc_string[i:i+5] == "$csr{":
                if buffer:
                    parsed_descriptions.append(Description(type_="string", value=buffer, resolved=resolved))
                    buffer = ""
                i += 5
                nested_content, i = self.extract_nested_content(desc_string, i)
                parsed_descriptions.append(Description(type_="csr", value="csr", resolved=resolved, nested_descriptions=self.parse_description_string(nested_content, instructionGroup, resolved=resolved)))
            elif desc_string[i:i+10] == "$bitfield{":
                if buffer:
                    parsed_descriptions.append(Description(type_="string", value=buffer, resolved=resolved))
                    buffer = ""
                i += 10
                nested_content, i = self.extract_nested_content(desc_string, i, single_level=True)
                if nested_content not in instructionGroup.bitfields:
                    instructionGroup.addBitfield(nested_content)
                parsed_descriptions.append(Description(type_="bitfield", value=nested_content, resolved=resolved))
            elif desc_string[i:i+10] == "$resolved{":
                if buffer:
                    parsed_descriptions.append(Description(type_="string", value=buffer, resolved=resolved))
                    buffer = ""
                i += 10
                nested_content, i = self.extract_nested_content(desc_string, i)
                parsed_descriptions.extend(self.parse_description_string(nested_content, instructionGroup, resolved=True))
            else:
                buffer += desc_string[i]
                i += 1

        if buffer:
            parsed_descriptions.append(Description(type_="string", value=buffer, resolved=resolved))
        
        return parsed_descriptions

    def extract_nested_content(self, desc_string, start_idx, single_level=False):
        nested_content = ""
        open_braces = 1
        i = start_idx

        while i < len(desc_string) and open_braces > 0:
            if desc_string[i] == '{' and not single_level:
                open_braces += 1
            elif desc_string[i] == '}':
                open_braces -= 1
                if open_braces == 0:
                    break
            nested_content += desc_string[i]
            i += 1

        return nested_content, i + 1