default_prefix = '((${ARCH_NAME}*)cpu)->'
prefixes = {
    'PC': 'cpu->',
    'X': '*((${ARCH_NAME}*)cpu)->'
}

rename_static = {
    'PC': 'ic.current_address_'
}

rename_dynamic = {
    'PC': 'cpu->instructionPointer'
}

exception_mapping = {
    (0, 0): 'ETISS_RETURNCODE_IBUS_READ_ERROR',
    (0, 2): 'ETISS_RETURNCODE_ILLEGALINSTRUCTION',
    (0, 11): 'ETISS_RETURNCODE_SYSCALL',
    (0, 3): 'ETISS_RETURNCODE_CPUFINISHED'
}