${builder_.getLicenseHeader()}

#include "${traceModel_.name}_Printer.h"

#include "Printer.h"

#include "${traceModel_.name}_Channel.h"

#include <iostream>
#include <iomanip>

extern InstructionPrinterSet* ${traceModel_.name}_InstrPrinterSet;

${traceModel_.name}_Printer::${traceModel_.name}_Printer(): Printer("${traceModel_.name}_Printer", ${traceModel_.name}_InstrPrinterSet)
{}

void ${traceModel_.name}_Printer::connectChannel(Channel* ch_)
{
  ${traceModel_.name}_Channel* channel = static_cast<${traceModel_.name}_Channel*>(ch_);
  
  % for trVal_i in traceModel_.getAllTraceValues():
  ${trVal_i.name}_ptr = channel->${trVal_i.name};
  % endfor
}

std::string ${traceModel_.name}_Printer::getPrintHeader(void)
{
  std::stringstream caption_strs;	
  % for trVal_i in traceModel_.getAllTraceValues():
  caption_strs << ${builder_.getStreamSetupCaption(trVal_i)} << "${trVal_i.name}" << ${builder_.getSeparater()};
  % endfor
  caption_strs << std::endl;

  return caption_strs.str();
}