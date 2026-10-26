"""Deterministic, non-mutating planning for 32-bit custom instruction encodings.

The prototype conservatively allocates one namespace across all model containers.
It never widens logical operands or infers operand attributes from their names.
"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Tuple

from ...metamodel import arch, type_info
from ...metamodel.attribute_info import OperandAttribute as Attr


class EncodingError(ValueError):
    """An encoding request cannot be satisfied without changing its contract."""


@dataclass(frozen=True)
class EncodingPolicy:
    opcodes: Tuple[int, ...] = (0x0B, 0x2B, 0x5B, 0x7B)
    # Additional occupied (code, mask) patterns, e.g. extension reservations.
    reservations: Tuple[Tuple[int, int], ...] = ()

    def __post_init__(self):
        if not self.opcodes or len(set(self.opcodes)) != len(self.opcodes):
            raise EncodingError("opcodes must be nonempty and unique")
        if any(x not in (0x0B, 0x2B, 0x5B, 0x7B) for x in self.opcodes):
            raise EncodingError("riscv-custom32 supports only custom-0 through custom-3")
        for code, mask in self.reservations:
            validate_pattern(code, mask)


def validate_pattern(code, mask):
    if not isinstance(code, int) or not isinstance(mask, int) or not 0 <= code <= mask <= 0xFFFFFFFF or code & ~mask:
        raise EncodingError("invalid 32-bit code/mask pattern")


def overlaps(a, b):
    return ((a[0] ^ b[0]) & a[1] & b[1]) == 0


@dataclass(frozen=True)
class Field:
    name: str
    offset: int
    width: int
    signed: bool


@dataclass(frozen=True)
class Assignment:
    name: str
    layout: str
    code: int
    mask: int
    fields: Tuple[Field, ...]

    def encoding(self):
        """Emit metamodel fields without changing operand descriptors or behavior."""
        by_offset = {field.offset: field for field in self.fields}
        result = []
        bit = 0
        while bit < 32:
            field = by_offset.get(bit)
            if field:
                kind = type_info.TypeKind.INT if field.signed else type_info.TypeKind.UINT
                result.append(arch.BitField(field.name, arch.RangeSpec(field.width - 1, 0), kind))
                bit += field.width
            else:
                result.append(arch.BitVal(1, (self.code >> bit) & 1))
                bit += 1
        return list(reversed(result))

    def to_dict(self):
        return dict(name=self.name, layout=self.layout, code=self.code, mask=self.mask,
                    fields=[dict(name=f.name, offset=f.offset, width=f.width, signed=f.signed) for f in self.fields])


@dataclass(frozen=True)
class EncodingPlan:
    assignments: Tuple[Assignment, ...]
    errors: Tuple[str, ...] = ()

    def raise_for_errors(self):
        if self.errors:
            raise EncodingError("\n".join(self.errors))

    def explain(self):
        lines = [f"{a.name}: {a.layout}, code=0x{a.code:08x}, mask=0x{a.mask:08x}" for a in self.assignments]
        lines.extend("ERROR: " + error for error in self.errors)
        return "\n".join(lines) or "No unencoded instructions."

    def to_dict(self):
        return dict(version=1, assignments=[a.to_dict() for a in self.assignments], errors=list(self.errors))


def operand_requirements(instruction):
    regs_in, regs_out, immediates = [], [], []
    for name, operand in instruction.operands.items():
        attrs = operand.attributes
        kinds = [x for x in (Attr.IS_REG, Attr.IS_IMM) if x in attrs]
        dirs = [x for x in (Attr.IN, Attr.OUT, Attr.INOUT) if x in attrs]
        if len(kinds) != 1 or len(dirs) != 1:
            raise EncodingError(f"operand {name}: require exactly one kind (IS_REG/IS_IMM) and direction (IN/OUT/INOUT)")
        width = operand.size
        if not isinstance(width, int) or width <= 0:
            raise EncodingError(f"operand {name}: width must be a positive integer")
        if kinds[0] == Attr.IS_IMM:
            if dirs[0] != Attr.IN:
                raise EncodingError(f"operand {name}: immediate must be an input")
            immediates.append((name, width, operand.signed))
        else:
            if width != 5 or operand.signed:
                raise EncodingError(f"operand {name}: custom32 register selectors must be unsigned 5-bit operands")
            for attribute, allowed in (
                (Attr.REG_CLASS, {"GPR"}),
                (Attr.REG_TYPE, {"s32", "i32", "u32", "s64", "i64", "u64"}),
            ):
                if attribute in attrs:
                    values = [getattr(value, "value", value) for value in attrs[attribute]]
                    if len(values) != 1 or values[0] not in allowed:
                        raise EncodingError(f"operand {name}: unsupported {attribute.name} {values!r}")
            # INOUT has one physical selector, in the destination position.
            (regs_in if dirs[0] == Attr.IN else regs_out).append((name, width, False))
    return regs_in, regs_out, immediates


def candidates(instruction):
    sources, destinations, immediates = operand_requirements(instruction)
    # Standard-position layouts. Unused capacity becomes discriminator bits.
    layouts = (
        ("R", (15, 20), (7,), ((20, 5),)),
        ("I", (15,), (7,), ((20, 12),)),
        ("R4", (15, 20, 25), (7,), ()),
        ("R4I", (15, 20), (7,), ((25, 5),)),
        ("2D", (15, 20), (7, 25), ()),
        ("IMM17", (), (7,), ((15, 17),)),
    )
    for layout, src_slots, dst_slots, imm_slots in layouts:
        if len(sources) > len(src_slots) or len(destinations) > len(dst_slots):
            continue
        fields = [Field(name, offset, width, signed) for (name, width, signed), offset in
                  list(zip(sources, src_slots)) + list(zip(destinations, dst_slots))]
        # Split an immediate slot between multiple logical immediates, preserving widths.
        free_slots = [(offset, capacity) for offset, capacity in imm_slots]
        valid = True
        for name, width, signed in immediates:
            for index, (offset, capacity) in enumerate(free_slots):
                if width <= capacity and all(not (offset < f.offset + f.width and f.offset < offset + width) for f in fields):
                    fields.append(Field(name, offset, width, signed))
                    free_slots[index] = (offset + width, capacity - width)
                    break
            else:
                valid = False
                break
        if valid:
            yield layout, tuple(fields)


def available_codes(mask, opcodes, occupied):
    """Search discriminator bits, pruning subtrees covered by a reservation."""
    bits = [bit for bit in range(7, 32) if mask & (1 << bit)]

    def search(code, fixed, index):
        if any((other_mask & mask & fixed) == (other_mask & mask) and
               ((code ^ other_code) & other_mask & mask) == 0
               for other_code, other_mask in occupied):
            return
        if index == len(bits):
            if all(not overlaps((code, mask), other) for other in occupied):
                yield code
            return
        bit = 1 << bits[index]
        yield from search(code, fixed | bit, index + 1)
        yield from search(code | bit, fixed | bit, index + 1)

    for opcode in opcodes:
        yield from search(opcode, 0x7F, 0)


def plan_encodings(instructions, policy=None, existing=(), assignments=None):
    """Plan an iterable of unencoded instructions. Optional manifest pins assignments.

    Names must be unique. Existing encodings are (code, mask) pairs in this domain.
    Errors are collected and prevent application of the entire plan.
    """
    policy = policy or EncodingPolicy()
    occupied = list(existing) + list(policy.reservations)
    for pattern in occupied:
        validate_pattern(*pattern)
    manifest = assignments or {"version": 1, "assignments": []}
    if manifest.get("version") != 1 or manifest.get("errors"):
        raise EncodingError("expected a successful version 1 assignment manifest")
    pins = {}
    for item in manifest["assignments"]:
        if item["name"] in pins:
            raise EncodingError("duplicate manifest assignment: " + item["name"])
        pins[item["name"]] = item
    requests, errors = {}, []
    for instruction in instructions:
        if instruction.name in requests:
            errors.append(f"{instruction.name}: duplicate instruction name")
        requests[instruction.name] = instruction
    prepared = []
    for name, instruction in sorted(requests.items()):
        try:
            if instruction.has_encoding:
                raise EncodingError("instruction already has an encoding")
            options = list(candidates(instruction))
            if not options:
                raise EncodingError("no layout fits operand counts and widths (available: R, I, R4, R4I, 2D, IMM17)")
            prepared.append((name, options))
        except EncodingError as exc:
            errors.append(f"{name}: {exc}")
    result = []
    # Pins first so newly allocated instructions cannot steal their space.
    prepared.sort(key=lambda item: (item[0] not in pins, len(item[1]), item[0]))
    for name, options in prepared:
        found = None
        pin = pins.get(name)
        for layout, fields in options:
            variable = sum(((1 << f.width) - 1) << f.offset for f in fields)
            mask = 0xFFFFFFFF ^ variable
            if pin:
                validate_pattern(pin["code"], pin["mask"])
                proposed = Assignment(name, layout, pin["code"], mask, fields)
                choices = [pin["code"]] if proposed.to_dict() == pin and pin["code"] & 0x7F in policy.opcodes else []
            else:
                choices = available_codes(mask, policy.opcodes, occupied)
            for code in choices:
                if all(not overlaps((code, mask), other) for other in occupied):
                    found = Assignment(name, layout, code, mask, fields)
                    break
            if found:
                break
        if found:
            result.append(found)
            occupied.append((found.code, found.mask))
        else:
            errors.append(f"{name}: {'pinned assignment incompatible or occupied' if pin else 'no collision-free encoding remains'}")
    return EncodingPlan(tuple(sorted(result, key=lambda a: a.name)), tuple(errors))


def apply_encoding_plan(instructions, plan, copy=True):
    """Return encoded copies by default; validate everything before in-place updates."""
    plan.raise_for_errors()
    originals = list(instructions)
    by_name = {i.name: i for i in originals}
    if len(by_name) != len(originals) or set(by_name) != {a.name for a in plan.assignments}:
        raise EncodingError("plan does not match the instruction collection")
    staged = deepcopy(originals)
    staged_by_name = {i.name: i for i in staged}
    occupied = []
    for assignment in plan.assignments:
        instruction = staged_by_name[assignment.name]
        if instruction.has_encoding or (assignment.layout, assignment.fields) not in list(candidates(instruction)):
            raise EncodingError(f"{instruction.name}: model changed since planning")
        validate_pattern(assignment.code, assignment.mask)
        expected_mask = 0xFFFFFFFF ^ sum(((1 << f.width) - 1) << f.offset for f in assignment.fields)
        if assignment.mask != expected_mask or any(overlaps((assignment.code, assignment.mask), p) for p in occupied):
            raise EncodingError("invalid or overlapping plan assignment")
        occupied.append((assignment.code, assignment.mask))
        instruction.encoding = assignment.encoding()
        # Keep descriptor identities: behavior nodes may reference these objects.
        instruction._size, instruction.code, instruction.mask = 32, assignment.code, assignment.mask
    if copy:
        return staged
    for original, replacement in zip(originals, staged):
        original.encoding = replacement.encoding
        original._size, original.code, original.mask = 32, replacement.code, replacement.mask
    return originals


def model_instructions(model):
    """Collect shared instructions once, giving them stable qualified names."""
    from copy import copy
    records, existing = {}, []
    for category, containers in (("set", model.sets), ("core", model.cores)):
        for container_name, container in sorted(containers.items()):
            encoded = container.instructions.values() if isinstance(container.instructions, dict) else container.instructions
            for instruction in encoded:
                if instruction.size != 32:
                    raise EncodingError("prototype requires 32-bit existing instructions")
                existing.append((instruction.code, instruction.mask))
            for instruction in container.unencoded_instructions.values():
                if id(instruction) not in records:
                    proxy = copy(instruction)
                    proxy.name = f"{category}/{container_name}/{instruction.name}"
                    records[id(instruction)] = (proxy, instruction)
    return list(records.values()), existing


def plan_model(model, policy=None, assignments=None):
    records, existing = model_instructions(model)
    return plan_encodings([proxy for proxy, _ in records], policy, existing, assignments)


def apply_model_plan(model, plan):
    """Apply to a complete model copy, preserving aliases and updating containers."""
    result = deepcopy(model)
    records, existing = model_instructions(result)
    if any(overlaps((a.code, a.mask), pattern) for a in plan.assignments for pattern in existing):
        raise EncodingError("plan overlaps existing model encodings")
    encoded = apply_encoding_plan([proxy for proxy, _ in records], plan)
    for (_, instruction), replacement in zip(records, encoded):
        instruction.encoding = replacement.encoding
        instruction._size, instruction.code, instruction.mask = 32, replacement.code, replacement.mask
    for container in list(result.sets.values()) + list(result.cores.values()):
        for instruction in container.unencoded_instructions.values():
            if isinstance(container.instructions, dict):
                container.instructions[(instruction.code, instruction.mask)] = instruction
            else:
                container.instructions.append(instruction)
        if hasattr(container, "instr_classes"):
            container.instr_classes.update(instruction.size for instruction in container.unencoded_instructions.values())
        container.unencoded_instructions.clear()
        if hasattr(container, "_instructions_by_ext"):
            container._instructions_by_ext = None
        if hasattr(container, "_instructions_by_class"):
            container._instructions_by_class = None
    return result
