import re
import pickle

repl_re = r'''InstructionDefinition (?P<instr_def_name>\S*)\s*\(
\s*(?P<instr_arch>\S*),
\s*"(?P<instr_name>\S*)",
\s*\(uint\d\d?_t\)\s*(?P<code>\S*),
\s*\(uint\d\d?_t\)\s*(?P<mask>\S*),
(?P<operation>.*?),
0,
(?P<asm_printer>.*?)
\);
'''

with open('/home/wysiwyng/work/coredsl/coredsl-models/armv6m/gen_output/ARMv6MInstr.pickle', 'rb') as f:
    instrs = pickle.load(f)

new_opcodes = sorted(list(instrs.keys()))

with open('/home/wysiwyng/work/etiss-arm/ArchImpl/ARMv6M/ARMv6MArch.cpp', 'r+') as f:
    text = f.read()

matches = list(re.finditer(repl_re, text, re.DOTALL))
old_opcodes = sorted([(int(m.group('code'), 16), int(m.group('mask'), 16)) for m in matches])

not_in_new = set(old_opcodes).difference(new_opcodes)
not_in_old = set(new_opcodes).difference(old_opcodes)

    #instr = instrs[(int(m1.group('code'), 16), int(m1.group('mask'), 16))]



pass