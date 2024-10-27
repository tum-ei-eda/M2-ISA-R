/*
 * Copyright 2022 Chair of EDA, Technical University of Munich
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *	 http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/********************* AUTO GENERATE FILE (create by M2-ISA-R-Perf) *********************/

#include "Printer.h"
#include "Channel.h"

#include "${traceModel_.name}_Printer.h"

#include <sstream>
#include <string>
#include <iomanip>

InstructionPrinterSet *${traceModel_.name}_InstrPrinterSet = new InstructionPrinterSet("${traceModel_.name}_InstrPrinterSet");

% for type_i in traceModel_.getAllInstructionTypes():
static InstructionPrinter *instrPrinter_${type_i.name} = new InstructionPrinter(
  ${traceModel_.name}_InstrPrinterSet,
  "${type_i.name}",
  ${type_i.identifier},
  [](Printer* printer_){
    std::stringstream ret_strs;
    ${traceModel_.name}_Printer* printer = static_cast<${traceModel_.name}_Printer*>(printer_);
    % for trVal_i in traceModel_.getAllTraceValues():
    % if type_i.getMapping(trVal_i) is not None:
    ret_strs << ${builder_.getStreamSetup(trVal_i)} << printer->get_${trVal_i.name}() << ${builder_.getSeparater()};
    % else:
    ret_strs << ${builder_.getEmptyStream(trVal_i)} << ${builder_.getSeparater()};
    % endif
    % endfor
    return ret_strs.str();
  }
);
% endfor
