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

#!/usr/bin/env python3

import argparse
import pathlib
import pickle

from .frontend.Parser import Parser
from .backend.CodeGenerator import CodeGenerator
from .common import common as cf # type: ignore

from ...metamodel import M2_METAMODEL_VERSION, M2Model

# Class to keep folder-structure related information
class FileDict:

    def __init__(self, outDir_, modelName_):

        templateDir = pathlib.Path(__file__).parents[0] / "backend" / "templates"
        outDir = pathlib.Path(outDir_) / modelName_

        self.dict={}
        self.dict["ChannelHeader"] = {  "Template" : templateDir / "channel/include/channel.mako",
                                        "OutFile" : cf.createOrReplaceDir(outDir / "channel/include") / (modelName_ + "_Channel.h")}
        self.dict["ChannelSource"] = {  "Template" : templateDir / "channel/src/channel.mako",
                                        "OutFile" : cf.createOrReplaceDir(outDir / "channel/src") / (modelName_ + "_Channel.cpp")}
        self.dict["MonitorHeader"] = {  "Template" : templateDir / "monitor/include/monitor.mako",
                                        "OutFile" : cf.createOrReplaceDir(outDir / "monitor/include") / (modelName_ + "_Monitor.h")}
        self.dict["MonitorSource"] = {  "Template" : templateDir / "monitor/src/monitor.mako",
                                        "OutFile" : cf.createOrReplaceDir(outDir / "monitor/src") / (modelName_ + "_Monitor.cpp")}
        self.dict["InstructionMonitorsSource"] = {  "Template" : templateDir / "monitor/src/instructionMonitors.mako",
                                        "OutFile" : self.dict["MonitorSource"]["OutFile"].parent / (modelName_ + "_InstructionMonitors.cpp")}
        self.dict["PrinterHeader"] = {  "Template" : templateDir / "printer/include/printer.mako",
                                        "OutFile" : cf.createOrReplaceDir(outDir / "printer/include") / (modelName_ + "_Printer.h")}
        self.dict["PrinterSource"] = {  "Template" : templateDir / "printer/src/printer.mako",
                                        "OutFile" : cf.createOrReplaceDir(outDir / "printer/src") / (modelName_ + "_Printer.cpp")}
        self.dict["InstructionPrintersSource"] = {  "Template" : templateDir / "printer/src/instructionPrinters.mako",
                                        "OutFile" : self.dict["PrinterSource"]["OutFile"].parent / (modelName_ + "_InstructionPrinters.cpp")}

    def getTemplate(self, name_):
        return self.__get(name_, "Template")

    def getOutFile(self, name_):
        return self.__get(name_, "OutFile")

    def __get(self, name_, type_):
        return self.dict[name_][type_]

def setup():

    argParser = argparse.ArgumentParser()
    argParser.add_argument("description_file", help="Path to file containing the json description of the trace.")
    argParser.add_argument('M2_model', help="A .m2isarmodel file containing the models to generate.")
    argParser.add_argument("-o", "--output_dir", help="Directory to store generated trace-model.")
    args = argParser.parse_args()

    # resolve model paths
    abs_top_level = pathlib.Path(args.M2_model).resolve()
    search_path = abs_top_level.parent.parent
    M2model_fname = abs_top_level


    if abs_top_level.suffix == ".core_desc":
        search_path = abs_top_level.parent
        model_path = search_path.joinpath('gen_model')

        if not model_path.exists():
            raise FileNotFoundError('Models not generated!')
        M2model_fname = model_path / (abs_top_level.stem + '.m2isarmodel')

    with open(M2model_fname, 'rb') as f:
        M2model_obj: M2Model = pickle.load(f)

    if M2model_obj.model_version != M2_METAMODEL_VERSION:
        raise TypeError("Loaded model version mismatch")

    return args.description_file, M2model_obj, args.output_dir

def main():
    
    descriptionFile_, m2model_, outdir_= setup()
    
    # Find pathes for json-description and output-directory
    descriptionFile = pathlib.Path(descriptionFile_).resolve()
    if outdir_ is not None:
        outdir = pathlib.Path(outdir_).resolve()
    else:
        outdir = None

    # Parse json-description to trace-model
    print("")
    print("-- Generation TraceModel from JSON-file --")
    tracemodel_ = Parser().parse(descriptionFile)

    print()
    print("-- Creating file-dictionary --")
    outdir = outdir / 'code'
    fileDict = FileDict(outdir, tracemodel_.name)

    # Constructiong code generator
    try:
        m2_model_ = m2model_.cores[tracemodel_.core]
    except KeyError as e:
        raise RuntimeError(f"M2IASR model does not contain a core {e.args[0]}")
    codeGen = CodeGenerator(tracemodel_, m2_model_, fileDict)

    print()
    print("-- Generating code for trace-channel --")
    codeGen.generate("ChannelHeader")
    codeGen.generate("ChannelSource")
    
    print()
    print("-- Generating code for trace-monitor --")
    codeGen.generate("MonitorHeader")
    codeGen.generate("MonitorSource")
    codeGen.generate("InstructionMonitorsSource")

    print()
    print("-- Generating code for trace-printer --")
    codeGen.generate("PrinterHeader")
    codeGen.generate("PrinterSource")
    codeGen.generate("InstructionPrintersSource")

    return tracemodel_
            
# Run this if called stand-alone (i.e. this file is directly called)
if __name__ == '__main__':
    main()
