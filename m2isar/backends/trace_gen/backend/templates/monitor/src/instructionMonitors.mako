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

/********************* AUTO GENERATE FILE (create by TraceGenerator) *********************/

#include "Monitor.h"

#include "etiss/Instruction.h"

#include <sstream>
#include <string>

InstructionMonitorSet *${traceModel_.name}_InstrMonitorSet = new InstructionMonitorSet("${traceModel_.name}_InstrMonitorSet");

% for instr_i in traceModel_.getAllInstructions():
static InstructionMonitor *${builder_.getInstrMonitorName(instr_i.name)} = new InstructionMonitor(
  ${traceModel_.name}_InstrMonitorSet,
  "${instr_i.name}",
  [](etiss::instr::BitArray &ba, etiss::instr::Instruction &instr, etiss::instr::InstructionContext &ic){
    std::stringstream ret_strs;
    <%include file="bitfields.mako" args="instr_ = instr_i"/>\
    ret_strs << "${builder_.getBufferName("typeId")}[*${builder_.getInstrCntName()}] = " << ${instr_i.getInstructionType().identifier} << ";\n";
    % for map_i in instr_i.getAllPreMappings():
    <%include file="traceValueMonitor.mako" args="map_ = map_i, builder_ = builder_"/>\
    % endfor
    ret_strs << "*${builder_.getInstrCntName()} += 1;\n"; // TODO: InstrCnt should be set in the post-print-function (see below). Currently set here, to makes sure that it is set, even if instruction triggers a return
    return ret_strs.str();
  },
  [](etiss::instr::BitArray &ba, etiss::instr::Instruction &instr, etiss::instr::InstructionContext &ic){
    std::stringstream ret_strs;
    <%include file="bitfields.mako" args="instr_ = instr_i"/>\
    ret_strs << "*${builder_.getInstrCntName()} -= 1;\n"; // TODO: Hack! Needed as long as instrCnt is set by pre-print-function (see above)
    % for map_i in instr_i.getAllPostMappings():
    <%include file="traceValueMonitor.mako" args="map_ = map_i, builder_ = builder_"/>\
    % endfor
    ret_strs << "*${builder_.getInstrCntName()} += 1;\n";
    return ret_strs.str();
  }
);

% endfor
