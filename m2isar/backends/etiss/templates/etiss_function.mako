## SPDX-License-Identifier: Apache-2.0
##
## This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
##
## Copyright (C) 2022
## Chair of Electrical Design Automation
## Technical University of Munich
\
% if not static:

#ifndef ETISS_ARCH_STATIC_FN_ONLY
% endif
static inline ${return_type} ${fn_name}(${args_list})${';' if not operation else ''}
% if operation:
{
${operation}
}
% endif
% if not static:
#endif
% endif
