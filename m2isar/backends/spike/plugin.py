# SPDX-License-Identifier: Apache-2.0
"""Generate standalone Spike extensions for a deliberately bounded RV32/RV64 subset."""
import logging
import re
import copy
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

    def has_signed_operand(self, node):
        """Conservatively detect signed values before C++ integer promotions."""
        if getattr(getattr(node, "ty", None), "kind", None) == TypeKind.INT:
            return True
        if isinstance(node, behav.NamedReference):
            ref = node.reference
            return (getattr(ref, "signed", False) or
                    getattr(getattr(ref, "ty", None), "kind", None) == TypeKind.INT)
        if isinstance(node, behav.Group):
            return self.has_signed_operand(node.expr)
        if isinstance(node, behav.BinaryOperation):
            return self.has_signed_operand(node.left) or self.has_signed_operand(node.right)
        if isinstance(node, behav.UnaryOperation):
            return self.has_signed_operand(node.right)
        return False

    def expr(self, node):
        if isinstance(node, behav.TypeConv):
            ty = node.ty
            if ty is None or ty.kind not in (TypeKind.UINT, TypeKind.INT) or not 1 <= ty.size <= 64:
                raise Unsupported("cast requires an integer width of 1..64 bits")
            value = f"(uint64_t({self.expr(node.expr)}) & UINT64_C({(1 << ty.size) - 1}))"
            if ty.kind == TypeKind.INT:
                if ty.size == 64:
                    return f"int64_t({value})"
                sign = 1 << (ty.size - 1)
                return f"(int64_t({value} ^ UINT64_C({sign})) - INT64_C({sign}))"
            return value
        if isinstance(node, behav.Literal) and isinstance(node.value, int):
            if node.ty.kind == TypeKind.INT:
                value = int(node.value)
                if not -(1 << 63) <= value < (1 << 63):
                    raise Unsupported("signed literal outside int64 range")
                if value == -(1 << 63):
                    return "(-INT64_C(9223372036854775807) - INT64_C(1))"
                return f"{'-' if value < 0 else ''}INT64_C({abs(value)})"
            return f"UINT64_C({int(node.value) & ((1 << 64) - 1)})"
        if isinstance(node, behav.Group):
            return f"({self.expr(node.expr)})"
        if isinstance(node, behav.NamedReference):
            ref = node.reference
            if isinstance(ref, arch.Variable):
                self.local_type(ref)
                return "m2_local_" + identifier(ref.name)
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
            zero_equality = node.op.value in {"==", "!="} and any(
                isinstance(value, behav.Literal) and value.value == 0
                for value in (node.left, node.right)
            )
            if (node.op.value in {"==", "!=", "<", ">", "<=", ">="}
                    and self.has_signed_operand(node) and not zero_equality):
                raise Unsupported("comparisons involving signed operands are unsupported")
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

    def local_type(self, variable):
        ty = variable.ty
        if ty.kind != TypeKind.UINT or not 1 <= ty.size <= 64:
            raise Unsupported("local variables require unsigned integer widths of 1..64 bits")
        return ty

    def local_value(self, variable, expression):
        ty = self.local_type(variable)
        return f"(uint64_t({expression}) & UINT64_C({(1 << ty.size) - 1}))"

    def statement(self, node):
        if isinstance(node, behav.Operation):
            return "\n".join(self.statement(s) for s in node.statements)
        if isinstance(node, behav.Conditional):
            if not node.conds or len(node.stmts) not in (len(node.conds), len(node.conds) + 1):
                raise Unsupported("malformed conditional")
            branches = []
            for index, condition in enumerate(node.conds):
                keyword = "if" if index == 0 else "else if"
                branches.append(f"{keyword} ({self.expr(condition)}) {{\n{self.statement(node.stmts[index])}\n}}")
            if len(node.stmts) > len(node.conds):
                branches.append(f"else {{\n{self.statement(node.stmts[-1])}\n}}")
            return " ".join(branches)
        if isinstance(node, behav.VarDefinition):
            self.local_type(node.var)
            return f"uint64_t m2_local_{identifier(node.var.name)};"
        if isinstance(node, behav.Assignment):
            if isinstance(node.target, behav.VarDefinition):
                variable = node.target.var
                value = self.local_value(variable, self.expr(node.expr))
                return f"uint64_t m2_local_{identifier(variable.name)} = {value};"
            if isinstance(node.target, behav.NamedReference) and isinstance(node.target.reference, arch.Variable):
                value = self.local_value(node.target.reference, self.expr(node.expr))
                return f"{self.expr(node.target)} = {value};"
            target = self.expr(node.target)
            value = self.expr(node.expr)
            if target.startswith("read_x("):
                return f"write_x(p, {self.expr(node.target.index)}, {value});"
            if target.startswith("ext->"):
                return f"{target} = uint{node.target.reference.ty.element_type.size}_t({value});"
            raise Unsupported("assignment target must be a register or custom state")
        raise Unsupported(f"statement {type(node).__name__}")


def is_pc_increment(block):
    """Recognize the base ISA's PC update, which Spike already performs."""
    statements = block.operation.statements
    if block.attributes or len(statements) != 1 or not isinstance(statements[0], behav.Assignment):
        return False
    assignment = statements[0]
    target = assignment.target
    if not isinstance(target, behav.NamedReference) or not getattr(target.reference, "is_pc", False):
        return False
    expr = assignment.expr
    while isinstance(expr, (behav.TypeConv, behav.Group)):
        expr = expr.expr
    return (isinstance(expr, behav.BinaryOperation) and expr.op.value == "+"
            and isinstance(expr.left, behav.NamedReference) and expr.left.reference is target.reference
            and isinstance(expr.right, behav.NamedReference)
            and isinstance(expr.right.reference, arch.Intrinsic)
            and expr.right.reference.name == "__encoding_size")


def generate_plugin(set_def, custom_only=False, strict=False):
    """Return C++ source; warn and omit each unsupported instruction."""
    if custom_only:
        set_def = copy.copy(set_def)
        set_def.always_blocks = {name: block for name, block in set_def.always_blocks.items()
                                 if not is_pc_increment(block)}
        set_def.instructions = {
            key: insn for key, insn in set_def.instructions.items()
            if insn.code is not None and insn.code & 0x7f in {0x0b, 0x2b, 0x5b, 0x7b}
        }
        if not set_def.instructions:
            raise Unsupported("model contains no encoded custom instructions")
        # Spike implements the base ISA, including its FPU and CSRs. Only state
        # referenced by the custom instructions belongs in the extension.
        referenced = set()
        def collect(node):
            if isinstance(node, (behav.NamedReference, behav.IndexedReference)):
                referenced.add(id(node.reference))
            if isinstance(node, behav.BaseNode):
                for value in vars(node).values():
                    if isinstance(value, behav.BaseNode):
                        collect(value)
                    elif isinstance(value, (list, tuple)):
                        for child in value:
                            collect(child)
        for instruction in set_def.instructions.values():
            collect(instruction.operation)
        for attribute in ("memories", "register_banks"):
            setattr(set_def, attribute, {
                key: mem for key, mem in getattr(set_def, attribute).items()
                if id(mem) in referenced or (isinstance(mem, arch.RegisterBank) and mem.is_main_reg)
            })
    if getattr(set_def, "always_blocks", {}):
        raise Unsupported("always blocks are unsupported by the Spike backend")
    name = identifier(set_def.name)
    main_banks = [mem for mem in list(set_def.memories.values()) + list(set_def.register_banks.values())
                  if isinstance(mem, arch.RegisterBank) and mem.is_main_reg]
    widths = {mem.ty.element_type.size for mem in main_banks}
    if len(widths) > 1 or (widths and not widths <= {32, 64}):
        raise Unsupported("main integer register banks must have a consistent 32- or 64-bit width")
    xlen = next(iter(widths), 32)
    for mem in main_banks:
        Translator(None, xlen).memory(mem, "0")
    declarations, resets = [], []
    member_names = {name}
    for mem in list(set_def.memories.values()) + list(set_def.register_banks.values()):
        if (isinstance(mem, arch.Register) and mem.is_pc) or (isinstance(mem, arch.Memory) and mem.is_main_mem) or (isinstance(mem, arch.RegisterBank) and mem.is_main_reg):
            continue
        # Validate state before emitting any source.
        Translator(None, xlen).memory(mem, "0")
        member = identifier(mem.name)
        if member in member_names:
            raise Unsupported(f"generated state name collision: {mem.name}")
        member_names.add(member)
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
            if callback in member_names:
                raise Unsupported("instruction name collides with extension class or custom state")
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
            descriptors.append("{" + f"{code:#x}, {mask:#x}, " + ", ".join([callback] * 4) + "}")
            accepted.append((code, mask))
            callback_names.add(callback)
        except Unsupported as exc:
            if strict:
                raise Unsupported(f"instruction {insn.name}: {exc}") from exc
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
const char* name() {{ return "{name}"; }}
const char* name() const {{ return "{name}"; }}
{chr(10).join(declarations)}
{name}() {{ {''.join(resets)} }}
void reset() {{ {''.join(resets)} }}
void reset(processor_t&) {{ reset(); }}
static reg_t read_x(processor_t* p, uint64_t i) {{
if (i >= 32) throw trap_illegal_instruction(0);
return xlen == 32 ? uint32_t(p->get_state()->XPR[i]) : p->get_state()->XPR[i];
}}
static void write_x(processor_t* p, uint64_t i, uint64_t v) {{
if (i >= 32) throw trap_illegal_instruction(0);
reg_t value = normalize(v);
#ifdef RISCV_ENABLE_COMMITLOG
if (p->get_log_commits_enabled()) p->get_state()->log_reg_write[i << 4] = {{value, 0}};
#endif
p->get_state()->XPR.write(i, value);
}}
template<typename T, size_t N>
static T& state_at(std::array<T, N>& state, uint64_t i, insn_t insn) {{
if (i >= N) throw trap_illegal_instruction(insn.bits());
return state[i];
}}
{chr(10).join(callbacks)}
std::vector<insn_desc_t> get_instructions() {{ return {{{','.join(descriptors)}}}; }}
std::vector<insn_desc_t> get_instructions(const processor_t&) {{ return get_instructions(); }}
std::vector<disasm_insn_t*> get_disasms() {{ return {{}}; }}
std::vector<disasm_insn_t*> get_disasms(const processor_t*) {{ return get_disasms(); }}
}};
REGISTER_EXTENSION({name}, []() {{ return new {name}; }})
'''
