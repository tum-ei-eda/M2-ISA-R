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

add_custom_command(
	TARGET $${}{PROJECT_NAME} POST_BUILD
	COMMAND $${}{CMAKE_COMMAND} -E copy
		"$${}{CMAKE_CURRENT_LIST_DIR}/$${}{PROJECT_NAME}Funcs.h"
		"$${}{ETISS_BINARY_DIR}/include/jit/Arch/$${}{PROJECT_NAME}"
)
INSTALL(FILES "$${}{CMAKE_CURRENT_LIST_DIR}/$${}{PROJECT_NAME}Funcs.h" DESTINATION "include/jit/Arch/$${}{PROJECT_NAME}")

# handle gdbserver xml files
if(EXISTS "$${}{CMAKE_CURRENT_SOURCE_DIR}/xml")
	add_custom_target(copy_$${}{PROJECT_NAME}_xml ALL
		COMMAND $${}{CMAKE_COMMAND} -E make_directory
			"$${}{CMAKE_CURRENT_LIST_DIR}/xml"
		COMMAND $${}{CMAKE_COMMAND} -E copy_directory
			"$${}{CMAKE_CURRENT_LIST_DIR}/xml"
			"$${}{ETISS_BINARY_DIR}/xml/$${}{PROJECT_NAME}"
	)
	add_dependencies($${}{PROJECT_NAME} copy_$${}{PROJECT_NAME}_xml)
	install(DIRECTORY $${}{CMAKE_CURRENT_SOURCE_DIR}/xml/ DESTINATION xml/$${}{PROJECT_NAME})
endif()

ETISSPluginArch($${}{PROJECT_NAME})
