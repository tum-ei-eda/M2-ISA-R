
% if not static:
#ifndef ETISS_ARCH_STATIC_FN_ONLY
% endif

static inline ${return_type} ${fn_name} (${args_list})
{
${operation}
}

% if not static:
#endif
% endif
