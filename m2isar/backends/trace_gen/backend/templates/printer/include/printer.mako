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
                   
#ifndef ${builder_.getHeaderDefinePrefix_Printer()}
#define ${builder_.getHeaderDefinePrefix_Printer()}

#include "Printer.h"

#include "Channel.h"

#include <string>
#include <cstdint>

class ${traceModel_.name}_Printer : public Printer
{
public:

  ${traceModel_.name}_Printer();

  virtual void connectChannel(Channel*);
  virtual std::string getPrintHeader(void);

  % for trVal_i in traceModel_.getAllTraceValues():
  % if trVal_i.dataType == "int":
  int get_${trVal_i.name}(void){ return ${trVal_i.name}_ptr[instrIndex]; };
  % elif trVal_i.dataType == "uint64_t":
  uint64_t get_${trVal_i.name}(void){ return ${trVal_i.name}_ptr[instrIndex]; };
  % elif trVal_i.dataType == "string":
  std::string get_${trVal_i.name}(void){ return ${trVal_i.name}_ptr[instrIndex]; };
  % endif
  % endfor

private:

  % for trVal_i in traceModel_.getAllTraceValues():
  % if trVal_i.dataType == "int":
  int* ${trVal_i.name}_ptr;
  % elif trVal_i.dataType == "uint64_t":
  uint64_t* ${trVal_i.name}_ptr;
  % elif trVal_i.dataType == "string":
  char (*${trVal_i.name}_ptr)[${builder_.getStringSize(trVal_i)}];
  % endif
  % endfor
};

#endif // ${builder_.getHeaderDefinePrefix_Printer()}