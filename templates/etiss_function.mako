
% if not static:
#ifndef ETISS_ARCH_STATIC_FN_ONLY
% endif

${return_type} ${fn_name} (${'ETISS_CPU * const cpu, ETISS_System * const system, void * const * const plugin_pointers, 'if not static else ''}${args_list})
{
${operation}
}

% if not static:
#endif
% endif
