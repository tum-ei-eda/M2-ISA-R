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

from mako.lookup import TemplateLookup
from mako.template import Template

from .CodeBuilder import CodeBuilder as Builder

class CodeGenerator:

    def __init__(self, model_, fileDict_):
        self.model = model_
        self.fileDict = fileDict_
        self.builder = Builder(model_)
        
    def generateMonitor(self, traceModel_):

        self.__generateTraceChannel(traceModel_)
        self.__generateMonitor(traceModel_)
        self.__generateInstructionMonitors(traceModel_)

    def generatePrinter(self, traceModel_):

        self.__generatePrinter(traceModel_)
        self.__generateInstructionPrinters(traceModel_)

    def generate(self, target_):

        templateDir = self.fileDict.getTemplate(target_).parent
        templateFile = self.fileDict.getTemplate(target_).name
        
        templateLookup = TemplateLookup(directories=[str(templateDir)])
        template = templateLookup.get_template(str(templateFile))
        code = template.render(**{"traceModel_" : self.model, "builder_" : self.builder})

        outFile = self.fileDict.getOutFile(target_)
        with outFile.open('w') as f:
            f.write(code)
