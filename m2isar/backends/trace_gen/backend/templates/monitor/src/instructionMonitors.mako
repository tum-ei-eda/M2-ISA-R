${builder_.getLicenseHeader()}

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
