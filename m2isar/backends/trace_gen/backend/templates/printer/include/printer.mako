${builder_.getLicenseHeader()}
                   
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