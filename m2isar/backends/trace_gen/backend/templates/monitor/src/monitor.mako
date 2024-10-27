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

/********************* AUTO GENERATE FILE (create by Trace-Generator) *********************/

#include "${traceModel_.name}_Monitor.h"

#include "softwareEval-backends/Channel.h"

#include <sstream>
#include <string>
#include <stdbool.h>
#include <cstdint>

extern "C"
{
  uint64_t *${builder_.getInstrCntName()};
  uint64_t *${builder_.getBufferName("typeId")};
  % for trVal_i in traceModel_.getAllTraceValues():
  % if trVal_i.dataType == "int":
  int *${builder_.getBufferName(trVal_i.name)};
  % elif trVal_i.dataType == "uint64_t":
  uint64_t *${builder_.getBufferName(trVal_i.name)};
  % elif trVal_i.dataType == "string":
  char (*${builder_.getBufferName(trVal_i.name)})[${builder_.getStringSize(trVal_i)}];
  % endif
  % endfor
}

extern InstructionMonitorSet* ${traceModel_.name}_InstrMonitorSet;

${traceModel_.name}_Monitor::${traceModel_.name}_Monitor(): Monitor("${traceModel_.name}_Monitor", ${traceModel_.name}_InstrMonitorSet)
{}

void ${traceModel_.name}_Monitor::connectChannel(Channel* channel_)
{
  Monitor::connectChannel(channel_);

  ${traceModel_.name}_Monitor_instrCnt = &(channel_->instrCnt);
  ${traceModel_.name}_Monitor_typeId_buffer = channel_->typeId;

  % for trVal_i in traceModel_.getAllTraceValues():
  % if trVal_i.dataType == "int":
  ${builder_.getBufferName(trVal_i.name)} = static_cast<int*>(channel_->getTraceValueHook("${trVal_i.name}"));
  % elif trVal_i.dataType == "uint64_t":
  ${builder_.getBufferName(trVal_i.name)} = static_cast<uint64_t*>(channel_->getTraceValueHook("${trVal_i.name}"));
  % elif trVal_i.dataType == "string":
  ${builder_.getBufferName(trVal_i.name)} = static_cast<char(*)[${builder_.getStringSize(trVal_i)}]>(channel_->getTraceValueHook("${trVal_i.name}"));
  % endif
  % endfor
}

<%
hasString = False
for trVal_i in traceModel_.getAllTraceValues():
    if trVal_i.dataType == "string":
       hasString = True
%>
std::string ${traceModel_.name}_Monitor::getBlockDeclarations(void) const
{
  std::stringstream ret_strs;
  % if hasString:
  ret_strs << "#include <string.h>\n";
  % endif
 
  ret_strs << "extern uint64_t *${builder_.getInstrCntName()};\n";
  ret_strs << "extern uint64_t *${builder_.getBufferName("typeId")};\n";

  % for trVal_i in traceModel_.getAllTraceValues():
  % if trVal_i.dataType == "int":
  ret_strs << "extern int *${builder_.getBufferName(trVal_i.name)};\n";
  % elif trVal_i.dataType == "uint64_t":
  ret_strs << "extern uint64_t *${builder_.getBufferName(trVal_i.name)};\n";
  % elif trVal_i.dataType == "string":
  ret_strs << "extern char (*${builder_.getBufferName(trVal_i.name)})[${builder_.getStringSize(trVal_i)}];\n";
  % endif
  % endfor

  return ret_strs.str();
}
