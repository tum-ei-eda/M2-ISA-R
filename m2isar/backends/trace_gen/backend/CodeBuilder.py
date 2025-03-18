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

from datetime import datetime
from typing import List, Union

from m2isar.metamodel import M2Model
from m2isar.metamodel import arch

class BitRange:
    """Represents the actual bit range of a bitfield within the instruction encoding."""
    def __init__(self, name: str, msb: int, lsb: int, offset: int):
        self.name = name
        self.msb = msb
        self.lsb = lsb
        self.offset = offset

    def __repr__(self):
        return f"BitRange(name='{self.name}', MSB={self.msb}, LSB={self.lsb}, offset={self.offset})"

class CodeBuilder:
# The idea of this class is to contain output code specific
# information (e.g. channel sizes, naming conventions, etc)

    __MAX_STRING_SIZE_DEFAULT = 100
    __MAX_INT_SIZE = 16
    __CHANNEL_SIZE = 100
    
    def __init__(self, trace_model_, m2_coreDef_model_):
        self.trace_model = trace_model_
        self.m2_coreDef_model = m2_coreDef_model_
        
    def getStringSize(self, trVal_):
        return self.__getValidStringSize(trVal_)
    
    def getChannelSize(self):
        return self.__CHANNEL_SIZE

    def getBufferName(self, trVal_):
        return (self.__getMonitorPrefix() + trVal_ + "_buffer")

    def getInstrCntName(self):
        return (self.__getMonitorPrefix() + "instrCnt")

    def getInstrMonitorName(self, instrName_):
        return ("instrMonitor_" + instrName_.replace('.', '_'))

    def getStreamSetup(self, trVal_):
        if(trVal_.dataType == "int"):
            return self.__getStreamSetupInt()
        elif(trVal_.dataType == "uint64_t"):
            return self.__getStreamSetupInt()
        elif(trVal_.dataType == "string"):
            return self.__getStreamSetupString(self.__getValidStringSize(trVal_))
        else:
            raise TypeError("Cannot call CodeBuilder::getStreamSetup with type %s" %trVal_.dataType)

    def getEmptyStream(self, trVal_):
        if(trVal_.dataType == "int") or (trVal_.dataType == "uint64_t"):
            return self.__getEmptyStreamWithSize(self.__MAX_INT_SIZE + 2)
        elif(trVal_.dataType == "string"):
            return self.__getEmptyStreamWithSize(self.__getValidStringSize(trVal_))
        else:
            raise TypeError("Cannot call CodeBuilder::getStreamSetup with type %s" %trVal_.dataType)

    def getStreamSetupCaption(self, trVal_):
        if(trVal_.dataType == "int") or (trVal_.dataType == "uint64_t"):
            return self.__getStreamSetupString(self.__MAX_INT_SIZE + 2) # NOTE: This won't work if name of tracevalue is longer than INT_SIZE + 2
        elif(trVal_.dataType == "string"):
            return self.__getStreamSetupString(self.__getValidStringSize(trVal_))
        else:
            raise TypeError("Cannot call CodeBuilder::getStreamSetup with type %s" %trVal_.dataType)
        
    def getSeparater(self):
        return "\" " + self.trace_model.getSeparator() + " \""

    def getDescriptionString(self, descriptions):
        result = ""
        previous_resolved = False
        for description in descriptions:
            if description.type == "pc":
                if description.resolved:
                    if not previous_resolved:
                        result += "<< "
                    result += "ic.current_address_"
                    previous_resolved = True
                else:
                    result += "<< \"cpu->instructionPointer\""
                    previous_resolved = False
            elif description.type == "asm":
                result += "instr.printASM(ba)"
                previous_resolved = False
            elif description.type == "code":
                if not previous_resolved:
                    result += "<< "
                result += "ba"
                previous_resolved = False
            elif description.type == "reg":
                result += f"<< \"*(({self.m2_coreDef_model.name}*)cpu)->X[\"" + self.getDescriptionString(description.nested_descriptions) + " << \"]\""
                previous_resolved = False
            elif description.type == "csr":
                result += f"<< \"{self.m2_coreDef_model.name}_csr_read(cpu, system, plugin_pointers, \"" + self.getDescriptionString(description.nested_descriptions) + " << \")\""
                previous_resolved = False
            elif description.type == "bitfield":
                if description.resolved:
                    if not previous_resolved:
                        result += "<< "
                    result += f"{description.value} "
                    previous_resolved = True
                else:
                    result += f"<< {description.value}"
                    previous_resolved = False
            elif description.type == "string":
                if description.resolved:
                    if not previous_resolved:
                        result += "<< "
                    result += f"{description.value}"
                    previous_resolved = True
                else:
                    result += f"<< \"{description.value}\""
                    previous_resolved = False

        return result

    def getLicenseHeader(self):
        ret = "/*\n"
        ret += f"* Copyright {datetime.today().year} Chair of EDA, Technical University of Munich\n"
        ret += "*\n"
        ret += "* Licensed under the Apache License, Version 2.0 (the \"License\");\n"
        ret += "* you may not use this file except in compliance with the License.\n"
        ret += "* You may obtain a copy of the License at\n"
        ret += "*\n"
        ret += "*	 http://www.apache.org/licenses/LICENSE-2.0\n"
        ret += "*\n"
        ret += "* Unless required by applicable law or agreed to in writing, software\n"
        ret += "* distributed under the License is distributed on an \"AS IS\" BASIS,\n"
        ret += "* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
        ret += "* See the License for the specific language governing permissions and\n"
        ret += "* limitations under the License.\n"
        ret += "*/\n"
        ret += "\n"
        ret += "/********************* AUTO GENERATE FILE (create by M2-ISA-R::Trace-Generator) *********************/\n"
        return ret

    def getHeaderDefinePrefix_Monitor(self):
        return ("SWEVAL_MONITOR_" + self.trace_model.name.upper() + "_MONITOR_H") 
    
    def getHeaderDefinePrefix_Channel(self):
        return (self.__getHeaderDefinePrefix_SWEvalBackends() + "_CHANNEL_H")

    def getHeaderDefinePrefix_Printer(self):
        return (self.__getHeaderDefinePrefix_SWEvalBackends() + "_PRINTER_H")
    
    def getAllBitRanges(self, instr_, bf_i):
        instruction = next((instr for key, instr in self.m2_coreDef_model.instructions.items() if instr.name == instr_), None)
        if not instruction:
            # print(f"Warning: Instruction '{instr_}' not found in original case format.")
            instruction = next((instr for key, instr in self.m2_coreDef_model.instructions.items() if instr.name == instr_.lower()), None)
        if not instruction:
            # print(f"Warning: Instruction '{instr_}' not found in lower case format.")
            instruction = next((instr for key, instr in self.m2_coreDef_model.instructions.items() if instr.name == instr_.upper()), None)
        if not instruction:
            # print(f"Warning: Instruction '{instr_}' not found in upper case format.")
            raise ValueError(f"Instruction '{instr_}' not found in any case format.")
        return [bitrange for bitrange in self.__calculate_bit_ranges(instruction) if bitrange.name == bf_i]
    
    ## HELPER FUNCTIONS
    
    def __getMonitorPrefix(self):
        return (self.trace_model.name + "_Monitor_")

    def __getStreamSetupInt(self):
        return ("\"0x\" << std::setfill(\'0\') << std::setw(" + str(self.__MAX_INT_SIZE) + ") << std::right << std::hex")

    def __getStreamSetupString(self, size_):
        return ("std::setfill(\' \') << std::setw(" + str(size_) + ") << std::left")
    
    def __getEmptyStreamWithSize(self, size_):
        return ("std::setfill(\'-\') << std::setw(" + str(size_) + ") << \"\"")

    def __getValidStringSize(self, trVal_):
        return trVal_.size if trVal_.size > 0 else self.__MAX_STRING_SIZE_DEFAULT

    def __getHeaderDefinePrefix_SWEvalBackends(self):
        return ("SWEVAL_BACKENDS_" + self.trace_model.name.upper())
        
    def __calculate_bit_ranges(self, instr) -> List[BitRange]:
        bit_ranges = []
        
        # Calculate total bit width of the instruction by summing lengths of all fields
        current_position = sum(field.length if isinstance(field, arch.BitVal) else field.range.length for field in instr.encoding)

        for field in instr.encoding:
            if isinstance(field, arch.BitField):
                # Calculate MSB and LSB based on current position and the field length
                current_position -= field.range.length
                LSB = current_position
                MSB = LSB + field.range.length - 1
                offset = field.range.lower_base

                # Create a BitRange object and add it to the list
                bit_ranges.append(BitRange(name=field.name, msb=MSB, lsb=LSB, offset=offset))
            else:
                # For BitVal, simply subtract its length from the current position
                current_position -= field.length

        return bit_ranges

