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

% for instrGr_i in traceModel_.getAllInstructionGroups():
% for instr_i in instrGr_i.getAllInstructions():
static InstructionMonitor *${builder_.getInstrMonitorName(instr_i)} = new InstructionMonitor(
  ${traceModel_.name}_InstrMonitorSet,
  "${instr_i.lower()}",
  [](etiss::instr::BitArray &ba, etiss::instr::Instruction &instr, etiss::instr::InstructionContext &ic){
    std::stringstream ret_strs;
    <%include file="bitfields.mako" args="instr_ = instr_i, bitfields = instrGr_i.getAllBitfields(), builder_ = builder_"/>\
    ret_strs << "${builder_.getBufferName("typeId")}[*${builder_.getInstrCntName()}] = " << ${instrGr_i.identifier} << ";\n";
    % for map_i in instrGr_i.getAllPreMappings():
    <%include file="traceValueMonitor.mako" args="map_ = map_i, builder_ = builder_"/>\
    % endfor
    % if instrGr_i.getAllPostMappings()==[]:
    ret_strs << "*${builder_.getInstrCntName()} += 1;\n";
    % endif
    return ret_strs.str();
  },
  [](etiss::instr::BitArray &ba, etiss::instr::Instruction &instr, etiss::instr::InstructionContext &ic){
    std::stringstream ret_strs;
    % if instrGr_i.getAllPostMappings()!=[]:
    <%include file="bitfields.mako" args="instr_ = instr_i, bitfields = instrGr_i.getAllBitfields(), builder_ = builder_"/>\
    % for map_i in instrGr_i.getAllPostMappings():
    <%include file="traceValueMonitor.mako" args="map_ = map_i, builder_ = builder_"/>\
    % endfor
    ret_strs << "*${builder_.getInstrCntName()} += 1;\n";
    % endif
    return ret_strs.str();
  }
);
% endfor
% endfor
