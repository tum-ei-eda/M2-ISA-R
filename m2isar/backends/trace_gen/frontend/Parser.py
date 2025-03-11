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

import json
import re

# import the MetaTraceModel from the trace model directory one level above the front-end directory
from ..tracemodel import MetaTraceModel

class Parser():

    def __init__(self):
        self.currentIdentifier = 0
        self.setIdAuto = True
        
    def parse(self, file_):

        # Read data from json-file
        with open(file_) as f:
            data = json.load(f)

        # Create "top" trace model
        trace_json = data['trace']
        trace_model = MetaTraceModel.Trace(trace_json['name'], trace_json['core'])

        # Try to read setId attribute
        try:
            setIdAttr = trace_json['setId']
            if setIdAttr == "Automatic":
                self.setIdAuto = True
            elif setIdAttr == "Manual":
                self.setIdAuto = False
            else:
                print("ERROR: setId attribute is set to %s. The only currently supported flags are \"Automatic\" and \"Manual\"" % setIdAttr)
                self.setIdAuto = True
        except KeyError:
            self.setIdAuto = True

        if self.setIdAuto == True:
            self.currentIdentifier = 0

        # Try to read separator attribute
        try:
            trace_model.setSeparator(trace_json['separator'])
        except KeyError:
            pass
        
        # Create trace values (NOTE: Must do that before adding instructions / creating mappings!)
        for trVal_i in trace_json['traceValues']:
            try:
                trace_model.createAndAddTraceValue(trVal_i['name'], trVal_i["type"], trVal_i["size"])
            except KeyError:
                try:
                    trace_model.createAndAddTraceValue(trVal_i['name'], trVal_i["type"])
                except KeyError:
                    trace_model.createAndAddTraceValue(trVal_i['name'])
                
        # Create instruction-types for all instruction groups
        try:
            instructionGroups = data['trace']['instructionGroups']
        except KeyError:
            instructionGroups = []

        for instrGr_i in instructionGroups:
            instrType_model = trace_model.createAndAddInstructionGroup(instrGr_i['name'], self.__getId(instrGr_i))
            for instr_i in instrGr_i['instructions']:
                instrType_model.addInstruction(instr_i['name'])

            # Add mappings to instruction-type
            self.__addMapping(instrType_model, instrGr_i)
                
        # Create instruction-types for all singel instructions
        try:
            instructions = data['trace']['instructions']
        except KeyError:
            instructions = []

        for instr_i in instructions:
            instrType_model = trace_model.createAndAddInstructionGroup(instr_i['name'], self.__getId(instr_i))
            # why? what purpose does this serve and how does this help me out. 
            instrType_model.addInstruction(instr_i['name'])

            # Add mappings to instruction-type
            self.__addMapping(instrType_model, instr_i)
        
        return trace_model
    
    def __addMapping(self, instrTypeModel_, instrOrGroup_):
        for mapping_i in instrOrGroup_['mappings']:
            try:
                instrTypeModel_.createAndAddMapping(mapping_i['traceValue'], mapping_i['description'], mapping_i['position'])
            except KeyError:
                instrTypeModel_.createAndAddMapping(mapping_i['traceValue'], mapping_i['description'], "pre")


    def __getId(self, instrOrGroup_):
        retId = 0
        if self.setIdAuto == True:
            retId = self.currentIdentifier
            self.currentIdentifier += 1
        else:
            try:
                retId = instrOrGroup_['id']
            except KeyError:
                print("ERROR: SetId attribute set to \"Manual\", but no identifier specidied for instruction or instruction group %s" %instrOrGroup_['name'])
        return retId
