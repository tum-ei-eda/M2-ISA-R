## SPDX-License-Identifier: Apache-2.0
##
## This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
##
## Copyright (C) 2022
## Chair of Electrical Design Automation
## Technical University of Munich
\
# Generated on ${start_time}.
#
# This file contains the CMake build info for the ${core_name} core architecture.

PROJECT(${core_name})
FIND_PACKAGE(ETISS)

SET(CMAKE_BUILD_WITH_INSTALL_RPATH TRUE)
SET(CMAKE_INSTALL_RPATH "\$ORIGIN/../../include/jit/etiss/jit")

ADD_LIBRARY($${}{PROJECT_NAME} SHARED
	${core_name}Arch.cpp
	${core_name}ArchLib.cpp
	${core_name}ArchSpecificImp.cpp
	${core_name}Funcs.c
	% for f in arch_files:
	${f}
	% endfor
)

IF(ETISS_BINARY_DIR)
	ADD_CUSTOM_COMMAND(
		TARGET $${}{PROJECT_NAME} POST_BUILD
		COMMAND $${}{CMAKE_COMMAND} -E copy
			"$${}{CMAKE_CURRENT_LIST_DIR}/$${}{PROJECT_NAME}Funcs.h"
			"$${}{ETISS_BINARY_DIR}/include/jit/Arch/$${}{PROJECT_NAME}"
	)
ENDIF()
INSTALL(FILES "$${}{CMAKE_CURRENT_LIST_DIR}/$${}{PROJECT_NAME}Funcs.h" DESTINATION "include/jit/Arch/$${}{PROJECT_NAME}")

# handle gdbserver xml files
IF(EXISTS "$${}{CMAKE_CURRENT_SOURCE_DIR}/xml")
	ADD_CUSTOM_TARGET(copy_$${}{PROJECT_NAME}_xml ALL
		COMMAND $${}{CMAKE_COMMAND} -E make_directory
			"$${}{CMAKE_CURRENT_LIST_DIR}/xml"
		COMMAND $${}{CMAKE_COMMAND} -E copy_directory
			"$${}{CMAKE_CURRENT_LIST_DIR}/xml"
			"$${}{ETISS_BINARY_DIR}/xml/$${}{PROJECT_NAME}"
	)
	ADD_DEPENDENCIES($${}{PROJECT_NAME} copy_$${}{PROJECT_NAME}_xml)
	INSTALL(DIRECTORY $${}{CMAKE_CURRENT_SOURCE_DIR}/xml/ DESTINATION xml/$${}{PROJECT_NAME})
ENDIF()

ETISSPluginArch($${}{PROJECT_NAME})
