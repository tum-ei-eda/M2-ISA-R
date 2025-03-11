${builder_.getLicenseHeader()}

#ifndef ${builder_.getHeaderDefinePrefix_Monitor()}
#define ${builder_.getHeaderDefinePrefix_Monitor()}

#include "Monitor.h"
#include "softwareEval-backends/Channel.h"

#include <string>

class ${traceModel_.name}_Monitor : public Monitor
{
public:

  ${traceModel_.name}_Monitor();

  virtual void connectChannel(Channel*);
  virtual std::string getBlockDeclarations(void) const;
};

#endif // ${builder_.getHeaderDefinePrefix_Monitor()}