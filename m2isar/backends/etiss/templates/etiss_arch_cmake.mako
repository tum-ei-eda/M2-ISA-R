# Generated on ${start_time}.
#
# This file contains the CMake build info for the ${core_name} core architecture.

PROJECT(${core_name})

ADD_LIBRARY($${}{PROJECT_NAME} SHARED
	${core_name}Arch.cpp
	${core_name}ArchLib.cpp
	${core_name}ArchSpecificImp.cpp
	% for f in arch_files:
	${f}
	% endfor
)

FILE(COPY "$${}{CMAKE_CURRENT_LIST_DIR}/$${}{PROJECT_NAME}Funcs.h" DESTINATION "$${}{ETISS_BINARY_DIR}/include/jit/Arch/$${}{PROJECT_NAME}")
INSTALL(FILES "$${}{CMAKE_CURRENT_LIST_DIR}/$${}{PROJECT_NAME}Funcs.h" DESTINATION "include/jit/Arch/$${}{PROJECT_NAME}")

ETISSPluginArch($${}{PROJECT_NAME})