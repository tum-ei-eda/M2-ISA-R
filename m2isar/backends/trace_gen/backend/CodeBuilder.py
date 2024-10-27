# 
# Copyright 2022 Chair of EDA, Technical University of Munich
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

class CodeBuilder:
# The idea of this class is to contain output code specific
# information (e.g. channel sizes, naming conventions, etc)

    __MAX_STRING_SIZE_DEFAULT = 100
    __MAX_INT_SIZE = 16
    __CHANNEL_SIZE = 100
    
    def __init__(self, model_):
        self.model = model_

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
            return self.__getStreamSetupString(self.__MAX_INT_SIZE + 2) # TODO: This won't work if name of tracevalue is longer than INT_SIZE + 2
        elif(trVal_.dataType == "string"):
            return self.__getStreamSetupString(self.__getValidStringSize(trVal_))
        else:
            raise TypeError("Cannot call CodeBuilder::getStreamSetup with type %s" %trVal_.dataType)
        
    def getSeparater(self):
        return "\" " + self.model.getSeparator() + " \""

    def getDescriptionString(self, description_):
        ret = ""
        first = True
        for snip_i in description_.getAllDescriptionSnippets():
            if not first:
                ret += " << "
            else:
                first = False
            if not snip_i.isPreProcessed():
                ret += "\""
            ret += snip_i.getContent()
            if not snip_i.isPreProcessed():
                ret += "\""
        return ret

    def getHeaderDefinePrefix_Monitor(self):
        return ("SWEVAL_MONITOR_" + self.model.name.upper() + "_MONITOR_H") 
    
    def getHeaderDefinePrefix_Channel(self):
        return (self.__getHeaderDefinePrefix_SWEvalBackends() + "_CHANNEL_H")

    def getHeaderDefinePrefix_Printer(self):
        return (self.__getHeaderDefinePrefix_SWEvalBackends() + "_PRINTER_H")
    
    ## HELPER FUNCTIONS
    
    def __getMonitorPrefix(self):
        return (self.model.name + "_Monitor_")

    def __getStreamSetupInt(self):
        return ("\"0x\" << std::setfill(\'0\') << std::setw(" + str(self.__MAX_INT_SIZE) + ") << std::right << std::hex")

    def __getStreamSetupString(self, size_):
        return ("std::setfill(\' \') << std::setw(" + str(size_) + ") << std::left")
    
    def __getEmptyStreamWithSize(self, size_):
        return ("std::setfill(\'-\') << std::setw(" + str(size_) + ") << \"\"")

    def __getValidStringSize(self, trVal_):
        return trVal_.size if trVal_.size > 0 else self.__MAX_STRING_SIZE_DEFAULT

    def __getHeaderDefinePrefix_SWEvalBackends(self):
        return ("SWEVAL_BACKENDS_" + self.model.name.upper())
