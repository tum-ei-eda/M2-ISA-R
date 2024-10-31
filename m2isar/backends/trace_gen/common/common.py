# 
# Copyright 2023 Chair of EDA, Technical University of Munich
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#       http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import pathlib
import os
import errno
import shutil

def resolveOutDir(outDir_):
    if outDir_ is not None:
        return pathlib.Path(outDir_).resolve()
    else:
        return pathlib.Path(os.getcwd()).resolve() / "out"

def createOrReplaceDir(dir_):
    try:
        pathlib.Path(dir_).mkdir(parents=True)
    except OSError as e:
        if e.errno == errno.EEXIST:
            # TODO: Better handling here? Wait for user input?
            #print("WARNING: %s folder exists and is replaced" %(os.path.basename(os.path.normpath(str(dir_))))) 
            print("WARNING: %s folder exists and is replaced" %(os.path.normpath(str(dir_)))) 
            shutil.rmtree(dir_)
            pathlib.Path(dir_).mkdir(parents=True)
        else:
            raise
    return pathlib.Path(dir_).resolve()