/*
 * Copyright 2023 Chair of EDA, Technical University of Munich
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