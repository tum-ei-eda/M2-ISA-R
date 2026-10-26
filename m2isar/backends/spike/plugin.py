# SPDX-License-Identifier: Apache-2.0
"""Generate standalone Spike extensions for a deliberately bounded RV32/RV64 subset."""
import logging
import re
from ...metamodel import arch, behav
from ...metamodel.type_info import ArrayType, TypeKind

logger = logging.getLogger(__name__)


class Unsupported(ValueError):
    """The model cannot be translated faithfully by this backend."""


def identifier(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
        raise Unsupported(f"invalid C++ identifier: {name!r}")
    return "m2_" + name


class Translator:
    def __init__(self, instruction, xlen=32):
        self.instruction = instruction
        self.xlen = xlen

    def expr(self, node):
        if isinstance(node, behav.Literal) and isinstance(node.value, int):
            return f"UINT64_C({int(node.value) & ((1 << 64) - 1)})"
        if isinstance(node, behav.Group):
            return f"({self.expr(node.expr)})"
        if isinstance(node, behav.NamedReference):
            ref = node.reference
            if isinstance(ref, arch.Parameter):
                return str(ref.value)
            if isinstance(ref, arch.BitFieldDescr):
                return identifier(ref.name)
            if isinstance(ref, (arch.Memory, arch.RegisterBank, arch.Register)):
                if isinstance(ref, arch.Register) and ref.is_pc:
                    return "pc"
                if isinstance(ref.ty, ArrayType):
                    raise Unsupported("bank requires an index")
                return self.memory(ref, "0")
        if isinstance(node, behav.IndexedReference):
            if node.right is not None and node.right is not node.index:
                raise Unsupported("ranged memory access")
            return self.memory(node.reference, self.expr(node.index))
        if isinstance(node, behav.BinaryOperation):
            if node.op.value not in {"+", "-", "*", "&", "|", "^", "==", "!=", "<", ">", "<=", ">="}:
                raise Unsupported(f"operator {node.op.value}")
            return f"({self.expr(node.left)} {node.op.value} {self.expr(node.right)})"
        if isinstance(node, behav.UnaryOperation) and node.op.value in {"~", "!", "-", "+"}:
            return f"({node.op.value}({self.expr(node.right)}))"
        raise Unsupported(f"behavior node {type(node).__name__}")

    def memory(self, mem, index):
        if isinstance(mem, arch.Alias) or (isinstance(mem, arch.Memory) and mem.is_main_mem) or (isinstance(mem, arch.Register) and mem.is_pc):
            raise Unsupported(f"memory {mem.name}: aliases, main memory and indexed PC unsupported")
        if not isinstance(mem.ty, ArrayType):
            raise Unsupported(f"register {mem.name}: scalar custom state unsupported")
        if getattr(mem.ty.element_type, "kind", None) != TypeKind.UINT:
            raise Unsupported(f"memory {mem.name}: requires unsigned integer elements")
        if mem.ty.element_type.size not in (32, 64) or mem.ty.length is None or mem.ty.length <= 0:
            raise Unsupported(f"memory {mem.name}: requires 32- or 64-bit elements and zero-based finite range")
        if isinstance(mem, arch.RegisterBank) and mem.is_main_reg:
            if mem.ty.element_type.size != self.xlen:
                raise Unsupported("integer register width must match model XLEN")
            if mem.ty.length != 32:
                raise Unsupported("integer register bank must have 32 entries")
            return f"read_x(p, {index})"
        return f"ext->state_at(ext->{identifier(mem.name)}, {index}, insn)"

    def statement(self, node):
        if isinstance(node, behav.Operation):
            return "\n".join(self.statement(s) for s in node.statements)
        if isinstance(node, behav.Assignment):
            target = self.expr(node.target)
            value = self.expr(node.expr)
            if target.startswith("read_x("):
                return f"write_x(p, {self.expr(node.target.index)}, {value});"
            if target.startswith("ext->"):
                return f"{target} = uint{node.target.reference.ty.element_type.size}_t({value});"
            raise Unsupported("assignment target must be a register or custom state")
        raise Unsupported(f"statement {type(node).__name__}")


def generate_plugin(set_def):
    """Return C++ source; warn and omit each unsupported instruction."""
    name = identifier(set_def.name)
    main_banks = [mem for mem in list(set_def.memories.values()) + list(set_def.register_banks.values())
                  if isinstance(mem, arch.RegisterBank) and mem.is_main_reg]
    widths = {mem.ty.element_type.size for mem in main_banks}
    if len(widths) > 1 or (widths and not widths <= {32, 64}):
        raise Unsupported("main integer register banks must have a consistent 32- or 64-bit width")
    xlen = next(iter(widths), 32)
    declarations, resets = [], []
    for mem in list(set_def.memories.values()) + list(set_def.register_banks.values()):
        if (isinstance(mem, arch.Register) and mem.is_pc) or (isinstance(mem, arch.Memory) and mem.is_main_mem) or (isinstance(mem, arch.RegisterBank) and mem.is_main_reg):
            continue
        # Validate state before emitting any source.
        Translator(None, xlen).memory(mem, "0")
        declarations.append(f"std::array<uint{mem.ty.element_type.size}_t, {mem.ty.length}> {identifier(mem.name)}{{}};")
        resets.append(f"{identifier(mem.name)}.fill(0);")
        for key in mem._initval:
            index = 0 if key is None and mem.ty.length == 1 else key
            if index is None or not 0 <= index < mem.ty.length:
                raise Unsupported(f"initial state index outside {mem.name}")
            resets.append(f"{identifier(mem.name)}.at({index}) = uint{mem.ty.element_type.size}_t(UINT64_C({mem.initval(key) & ((1 << mem.ty.element_type.size) - 1)}));")
    callbacks, descriptors, accepted = [], [], []
    callback_names = set()
    for (code, mask), insn in set_def.instructions.items():
        try:
            callback = identifier(insn.name)
            if callback in callback_names:
                raise Unsupported("duplicate instruction name")
            if insn.size != 32 or mask & 0x7f != 0x7f or code & 0x7f not in {0x0b, 0x2b, 0x5b, 0x7b}:
                raise Unsupported("requires a 32-bit encoding with a fixed custom-0/1/2/3 opcode")
            if insn.attributes:
                raise Unsupported("instruction attributes")
            if any(((code ^ c) & mask & m) == 0 for c, m in accepted):
                raise Unsupported("encoding overlaps an already emitted instruction")
            fields = []
            offset = 0
            parts = {key: [] for key in insn.fields}
            field_masks = {key: 0 for key in insn.fields}
            for part in reversed(insn.encoding):
                width = part.range.length if isinstance(part, arch.BitField) else part.length
                if isinstance(part, arch.BitField):
                    if width <= 0 or part.range.lower < 0:
                        raise Unsupported(f"operand {part.name}: invalid bit range")
                    field_mask = ((1 << width) - 1) << part.range.lower
                    if field_masks[part.name] & field_mask:
                        raise Unsupported(f"operand {part.name}: repeated bits in encoding")
                    field_masks[part.name] |= field_mask
                    parts[part.name].append(f"(((insn.bits() >> {offset}) & {hex((1 << width)-1)}ULL) << {part.range.lower})")
                offset += width
            for field, descr in insn.fields.items():
                if descr.ty.size > 32 or descr.ty.size < 1:
                    raise Unsupported(f"operand {field}: requires 1..32 bits")
                val = " | ".join(parts[field])
                if descr.ty.kind == TypeKind.INT:
                    val = f"int64_t(({val}) ^ {1 << (descr.ty.size-1)}ULL) - {1 << (descr.ty.size-1)}LL"
                fields.append(f"const {'int64_t' if descr.ty.kind == TypeKind.INT else 'uint64_t'} {identifier(field)} = {val};")
            body = Translator(insn, xlen).statement(insn.operation)
            callbacks.append(f'''static reg_t {callback}(processor_t* p, insn_t insn, reg_t pc) {{
if (p->get_xlen() != {xlen}) throw trap_illegal_instruction(insn.bits());
auto* ext = static_cast<{name}*>(p->get_extension("{name}"));
{chr(10).join(fields)}
{body}
return normalize(pc + 4);
}}''')
            descriptors.append("{" + f"{code:#x}, {mask:#x}, " + ", ".join([callback, callback, "::illegal_instruction", "::illegal_instruction"] * 2) + "}")
            accepted.append((code, mask))
            callback_names.add(callback)
        except Unsupported as exc:
            logger.warning("Spike: skipping instruction %s: %s", insn.name, exc)
    for insn in getattr(set_def, "unencoded_instructions", {}).values():
        logger.warning("Spike: skipping instruction %s: no encoding", insn.name)
    return f'''// Generated M2-ISA-R Spike plugin. Requires Spike's matching C++ ABI.
#include "extension.h"
#include "trap.h"
#include <array>
#include <cstdint>
class {name} : public extension_t {{
public:
static constexpr unsigned xlen = {xlen};
static reg_t normalize(uint64_t value) {{
return xlen == 32 ? reg_t(int64_t(int32_t(uint32_t(value)))) : reg_t(value);
}}
const char* name() const override {{ return "{name}"; }}
{chr(10).join(declarations)}
{name}() {{ {''.join(resets)} }}
void reset(processor_t&) override {{ {''.join(resets)} }}
static reg_t read_x(processor_t* p, uint64_t i) {{
if (i >= 32) throw trap_illegal_instruction(0);
return xlen == 32 ? uint32_t(p->get_state()->XPR[i]) : p->get_state()->XPR[i];
}}
static void write_x(processor_t* p, uint64_t i, uint64_t v) {{
if (i >= 32) throw trap_illegal_instruction(0);
reg_t value = normalize(v);
if (p->get_log_commits_enabled()) p->get_state()->log_reg_write[i << 4] = {{value, 0}};
p->get_state()->XPR.write(i, value);
}}
template<typename T, size_t N>
static T& state_at(std::array<T, N>& state, uint64_t i, insn_t insn) {{
if (i >= N) throw trap_illegal_instruction(insn.bits());
return state[i];
}}
{chr(10).join(callbacks)}
std::vector<insn_desc_t> get_instructions(const processor_t&) override {{ return {{{','.join(descriptors)}}}; }}
std::vector<disasm_insn_t*> get_disasms(const processor_t* = nullptr) override {{ return {{}}; }}
}};
REGISTER_EXTENSION({name}, []() {{ return new {name}; }})
'''
