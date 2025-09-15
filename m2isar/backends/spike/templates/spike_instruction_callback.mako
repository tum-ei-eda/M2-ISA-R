${'\n'.join(misc_code)}
% for name, part in operation.generate().items():
${part}
%endfor
