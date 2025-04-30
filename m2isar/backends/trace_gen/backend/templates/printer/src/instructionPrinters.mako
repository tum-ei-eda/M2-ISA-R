${builder_.getLicenseHeader()}

#include "Printer.h"
#include "Channel.h"

#include "${traceModel_.name}_Printer.h"

#include <sstream>
#include <string>
#include <iomanip>

InstructionPrinterSet *${traceModel_.name}_InstrPrinterSet = new InstructionPrinterSet("${traceModel_.name}_InstrPrinterSet");

% for type_i in traceModel_.getAllInstructionGroups():
static InstructionPrinter *instrPrinter_${type_i.name} = new InstructionPrinter(
  ${traceModel_.name}_InstrPrinterSet,
  "${type_i.name}",
  ${type_i.identifier},
  [](Printer* printer_){
    std::stringstream ret_strs;
    ${traceModel_.name}_Printer* printer = static_cast<${traceModel_.name}_Printer*>(printer_);
    % for trVal_i in traceModel_.getAllTraceValues():
    % if type_i.getMapping(trVal_i) is not None:
    ret_strs << ${builder_.getStreamSetup(trVal_i)} << printer->get_${trVal_i.name}() << ${builder_.getSeparater()};
    % else:
    ret_strs << ${builder_.getEmptyStream(trVal_i)} << ${builder_.getSeparater()};
    % endif
    % endfor
    ret_strs << std::endl;
    return ret_strs.str();
  }
);
% endfor
