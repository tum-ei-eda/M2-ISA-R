${builder_.getLicenseHeader()}

#ifndef ${builder_.getHeaderDefinePrefix_Channel()}
#define ${builder_.getHeaderDefinePrefix_Channel()}

#include "Channel.h"

#include <string>
#include <stdbool.h>
#include <cstdint>

class ${traceModel_.name}_Channel: public Channel
{
public:

  ${traceModel_.name}_Channel() {};
  ~${traceModel_.name}_Channel() {};

  % for trVal_i in traceModel_.getAllTraceValues():
  % if trVal_i.dataType == "int":
  int ${trVal_i.name} [${builder_.getChannelSize()}];
  % elif trVal_i.dataType == "uint64_t":
  uint64_t ${trVal_i.name} [${builder_.getChannelSize()}];
  % elif trVal_i.dataType == "string":
  char ${trVal_i.name} [${builder_.getChannelSize()}] [${builder_.getStringSize(trVal_i)}];
  % endif
  % endfor

  virtual void *getTraceValueHook(std::string);
};

#endif // ${builder_.getHeaderDefinePrefix_Channel()}