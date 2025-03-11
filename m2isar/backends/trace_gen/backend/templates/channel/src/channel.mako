${builder_.getLicenseHeader()}

#include "${traceModel_.name}_Channel.h"

void *${traceModel_.name}_Channel::getTraceValueHook(std::string trVal_)
{
  % for trVal_i in traceModel_.getAllTraceValues():
  if(trVal_ == "${trVal_i.name}")
  {
    return ${trVal_i.name};
  }
  %endfor
  return nullptr;
}