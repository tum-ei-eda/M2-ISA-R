#
# Copyright (c) 2026 TUM Department of Electrical and Computer Engineering.
#
# This file is part of ISAAC Toolkit.
# See https://github.com/tum-ei-eda/isaac-toolkit.git for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Alternate generator using one encoding allocation domain across all sets.
from __future__ import annotations

import sys
import json
from types import SimpleNamespace
import yaml
import pickle
import logging
import argparse
import multiprocessing
from typing import Optional, Union, List
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import m2isar
import m2isar.metamodel.arch
from m2isar.metamodel import M2_METAMODEL_VERSION, M2Model

from m2isar.transforms.encode_instructions import (
    EncodingError, EncodingPolicy, apply_model_plan, plan_model,
)
from m2isar.transforms.encode_instructions.planner import overlaps, validate_pattern

from isaac_toolkit.logging import get_logger, set_log_level

logger = get_logger()


logging.getLogger("behav_builder").setLevel(logging.WARNING)
logging.getLogger("arch_builder").setLevel(logging.WARNING)
logging.getLogger("set_parser").setLevel(logging.WARNING)
logging.getLogger("visit_importer").setLevel(logging.WARNING)


def validate_instruction_sets(instructions_per_set):
    """Reject ambiguous generated decoding patterns, including unequal masks.

    This checks generated extension instructions, not imported base ISA files.
    It must run on lists before dictionary construction can hide duplicates.
    """
    occupied = []
    for set_name, instructions in sorted(instructions_per_set.items()):
        values = instructions.values() if isinstance(instructions, dict) else instructions
        for instruction in values:
            if not instruction.has_encoding or instruction.size != 32:
                raise EncodingError(f"{set_name}/{instruction.name}: expected a 32-bit encoding")
            pattern = (instruction.code, instruction.mask)
            validate_pattern(*pattern)
            for previous_name, previous_pattern in occupied:
                if overlaps(pattern, previous_pattern):
                    raise EncodingError(
                        f"overlapping generated encodings: {previous_name} and {set_name}/{instruction.name}"
                    )
            occupied.append((f"{set_name}/{instruction.name}", pattern))


def encode_instruction_sets(unencoded_per_set, existing_per_set=None, policy=None, assignments=None):
    """Plan all sets in one namespace, keeping names and input objects intact.

    Identical instruction names in different sets are qualified by plan_model.
    Returns (encoded instruction mappings by set, successful encoding plan).
    """
    existing_per_set = existing_per_set or {}
    validate_instruction_sets(existing_per_set)
    containers = {}
    for name in sorted(set(unencoded_per_set) | set(existing_per_set)):
        pending = unencoded_per_set.get(name, {})
        if any(key != instruction.name for key, instruction in pending.items()):
            raise EncodingError(f"{name}: unencoded mapping keys must match instruction names")
        old = existing_per_set.get(name, {})
        old_values = list(old.values() if isinstance(old, dict) else old)
        if set(pending) & {instruction.name for instruction in old_values}:
            raise EncodingError(f"{name}: instruction is both encoded and unencoded")
        containers[name] = SimpleNamespace(
            instructions={(instruction.code, instruction.mask): instruction for instruction in old_values},
            unencoded_instructions=dict(pending),
        )
    model = M2Model(M2_METAMODEL_VERSION, {}, containers, {})
    plan = plan_model(model, policy=policy, assignments=assignments)
    plan.raise_for_errors()
    encoded = apply_model_plan(model, plan)
    result = {name: container.instructions for name, container in encoded.sets.items()}
    validate_instruction_sets(result)
    return result, plan


def parse_generated_set(
    set_file,
    skip_errors: bool = False,
    extra_includes=None,
    add_mnemonic_prefix: bool = False,
    set_name: Optional[str] = None,
    auto_encoding: bool = False,
):
    from m2isar.frontends.coredsl2_set.parser import parse_cdsl2_set

    try:
        models = parse_cdsl2_set(set_file, extra_includes)
    except Exception as e:
        if skip_errors:
            logger.exception(e)
            return None, set_name, str(e)
        else:
            raise e
    instr_sets = list(models.values())
    set_names = list(models.keys())
    instr_sets = [
        instr_set
        for instr_set in instr_sets
        if len(instr_set.instructions) > 0 or len(instr_set.unencoded_instructions) > 0
    ]
    if len(instr_sets) == 1:
        instr_set = instr_sets[0]
        if set_name is None:
            set_name = set_names[0]
    else:
        instr_set = instr_sets[-1]
        if set_name is None:
            set_name = set_names[-1]
    ret = {}
    if auto_encoding:
        assert len(instr_set.instructions) == 0
        assert len(instr_set.unencoded_instructions) > 0
        for instr_def in instr_set.unencoded_instructions.values():
            name = instr_def.name
            if add_mnemonic_prefix:
                prefix = set_name.lower()
                name_lower = name.lower()
                mnemonic = f"{prefix}.{name_lower}"
                instr_def.mnemonic = mnemonic
            assert name not in ret, f"Duplicate instrustion name: {name}"
            ret[name] = instr_def
    else:
        assert len(instr_set.instructions) > 0
        assert len(instr_set.unencoded_instructions) == 0
        for instr_def in instr_set.instructions.values():
            name = instr_def.name
            if add_mnemonic_prefix:
                prefix = set_name.lower()
                name_lower = name.lower()
                mnemonic = f"{prefix}.{name_lower}"
                instr_def.mnemonic = mnemonic
            assert name not in ret, f"Duplicate instrustion name: {name}"
            ret[name] = instr_def
    # contributing_types.append(set_name_)
    # break  # TODO
    return ret, set_name, None


def get_cdsl_sets(ext: str, xlen: int = 32, compressed: bool = False):
    ext = ext.lower()
    cdsl_sets = {
        "i": [f"RV{xlen}I"] + ([f"RV{xlen}IC"] if compressed else []),
        "m": [f"RV{xlen}M"],
        "a": [f"RV{xlen}A"],
        "f": [f"RV{xlen}F"] + ([f"RV{xlen}FC"] if compressed else []),
        "d": [f"RV{xlen}D"] + ([f"RV{xlen}DC"] if compressed else []),
        "zifencei": ["Zifencei"],
        "zicsr": ["Zicsr"],
        "zve32x": ["Zve32x"],
        "zve32f": ["Zve32f"],
    }
    ret = cdsl_sets.get(ext, None)
    assert ret is not None, f"Lookup failed for ext: {ext}"
    return ret


def apply_etiss_overrides(sets: List[str], semihosting: bool = True):
    etiss_overrides = {
        "Zicsr": "tum_csr",
        "RV32A": "tum_rva",
        "RV64A": "tum_rva64",
        "RV64M": "tum_rvm",
    }
    ret = []
    new = []
    for orig in sets:
        replaced = etiss_overrides.get(orig, None)
        if replaced:
            new.append(replaced)
        else:
            ret.append(orig)
    if semihosting:
        new += ["tum_semihosting"]
    new += ["tum_ret"]
    return ret + new


def get_cdsl_includes(
    sets: List[str],
    base_dir: Union[str, Path] = "rv_base",
    tum_dir: Union[str, Path] = ".",
):
    # Reverse lookup required!
    cdsl_includes = {
        "RISCVBase.core_desc": ["RISCVBase"],
        # "RV32I.core_desc": ["RV32I", "Zicsr", "Zifencei", "RVNMode", "RVSMode", "RVDebug"],
        "RV64I.core_desc": ["RV64I"],
        "RVA.core_desc": ["RV32A", "RV64A"],
        "RVC.core_desc": [
            "RV32IC",
            "RV32FC",
            "RV32DC",
            "RV64IC",
            "RV64FC",
            "RV64DC",
            "RV128IC",
        ],
        "RVD.core_desc": ["RV32D", "RV64D"],
        "RVF.core_desc": ["RV32F", "RV64F"],
        "RVI.core_desc": [
            "RV32I",
            "RV64I",
            "Zicsr",
            "Zifencei",
            "RVNMode",
            "RVSMode",
            "RVDebug",
        ],
        "RVM.core_desc": ["RV32M", "RV64M"],
        "tum_rvm.core_desc": ["tum_rvm"],
        "tum_rva.core_desc": ["tum_rva", "tum_rva64"],
        "tum_mod.core_desc": ["tum_ret", "tum_csr", "tum_semihosting"],
        "RVV.core_desc": [
            "RV32V",
            "RV64V",
            "Zve32x",
            "Zve32f",
            "Zve64x",
            "Zve64f",
            "Zve64d",
        ],
    }
    ret = set()
    for set_name in sets:
        # print("set_name", set_name)
        matched = None
        for cdsl_file, cdsl_sets in cdsl_includes.items():
            if set_name in cdsl_sets:
                matched = cdsl_file
                break
        assert matched, f"Include could not be resolved for set: {set_name}"
        if "tum" in set_name.lower():
            base = Path(tum_dir)
        else:
            base = Path(base_dir)
        ret.add(str(base / matched))
    return ret


def get_includes_code(includes: List[Union[str, Path]], prefix: str = ""):
    ret = []
    for inc in includes:
        if isinstance(inc, Path):
            inc = str(inc)
        if ".core_desc" not in inc:
            inc = f"{inc}.core_desc"
        if inc[0] != "/":
            inc = f"{prefix}{inc}"
        new = f'import "{inc}"'
        ret.append(new)
    return "\n".join(ret)


# def generate_base_core
#     core_name: str = "IsaacCore",
#     xlen: int = 32,
#     ignore_etiss: bool = False,
#     semihosting: bool = True,
#     base_extensions: List[str] = ["i", "m", "a", "f", "d", "c", "zifencei"],
#     # etiss_overrides: List[str] = ["tum_csr", "tum_ret", "tum_rva", "tum_semihosting"],
# ):


def generate_etiss_core(
    sess: Session,
    workdir: Optional[Union[str, Path]] = None,
    gen_dir: Optional[Union[str, Path]] = None,
    index_files: Optional[List[Union[str, Path]]] = None,
    core_name: str = "IsaacCore",
    set_names: List[str] = ["XIsaac"],
    xlen: int = 32,
    ignore_etiss: bool = False,
    semihosting: bool = True,
    base_extensions: List[str] = ["i", "m", "a", "f", "d", "c", "zifencei", "zicsr"],
    auto_encoding: bool = True,
    split: bool = True,  # One set per new instr
    force: bool = False,
    base_dir: str = "rv_base",
    tum_dir: str = ".",
    skip_errors: bool = True,
    extra_includes: Optional[List[Union[str, Path]]] = None,
    add_mnemonic_prefix: bool = False,
    n_parallel: int = 1,
    new: bool = False,
    encoding_policy: str = "auto",
    encoding_manifest: Optional[Union[str, Path]] = None,
    encoding_opcodes=None,
    encoding_reservations=(),
):
    # Keep legacy code-generation dependencies separate from the planner API.
    from m2isar.backends.coredsl2_set.writer import gen_cdsl_code

    logger.info("Generating ETISS core...")
    if encoding_policy not in ("auto", "cfu"):
        raise ValueError(f"Unknown encoding policy: {encoding_policy}")
    cfu_encoder = None
    encoding_plan = None
    if encoding_policy == "cfu" and (encoding_opcodes is not None or encoding_reservations):
        raise ValueError("CFU has a fixed encoding policy; opcode/reservation overrides require auto policy")
    if encoding_policy == "auto" and not auto_encoding and (
        encoding_manifest is not None or encoding_opcodes is not None or encoding_reservations
    ):
        raise ValueError("Planner options require auto encoding")
    if encoding_policy == "cfu":
        from isaac_toolkit.generate.iss.cfu import CFUEncoder, validate_candidate
        if xlen != 32 or skip_errors:
            raise ValueError("CFU encoding requires RV32 and strict error handling")
        cfu_encoder = CFUEncoder(encoding_manifest or Path(workdir) / "cfu_manifest.json", allow_new=auto_encoding)
        # Reconstruct the original operand declarations, then reapply the exact
        # ledger assignment. The legacy encoded writer omits those declarations.
        # In --no-auto-encoding mode the encoder cannot allocate any new IDs.
        auto_encoding = True
    # artifacts = sess.artifacts
    # TODO: get combined_index.yml from artifacts!
    assert workdir is not None
    if not isinstance(workdir, Path):
        workdir = Path(workdir)
    assert workdir.is_dir()
    gen_dir = Path(gen_dir) if gen_dir is not None else workdir / "gen"
    gen_dir.mkdir(exist_ok=True)
    core_out_model_file = gen_dir / f"{core_name}.m2isarmodel"
    core_out_cdsl_file = gen_dir / f"{core_name}.core_desc"
    if index_files is None:
        if new:
            combined_index_file = workdir / "index.yml"  # if index_file is None else Path(index_file)
        else:
            combined_index_file = workdir / "combined_index.yml"  # if index_file is None else Path(index_file)
        index_files = [combined_index_file]
    else:
        assert isinstance(index_files, list)
        index_files = list(map(Path, index_files))
        assert len(index_files) > 0
        assert len(set_names) == len(index_files)
    generated_sets = []
    sub2files = defaultdict(dict)
    sub2new_files = defaultdict(dict)
    set_instr2sub_name = {}

    index_records = []
    for k, combined_index_file in enumerate(index_files):
        set_name = set_names[k]
        assert combined_index_file.is_file()
        with open(combined_index_file, "r") as f:
            index_data = yaml.safe_load(f)
        index_records.append((combined_index_file, index_data, k))
        for i, sub_data in enumerate(index_data["candidates"]):
            sub_artifacts = sub_data["artifacts"]
            # sub_properties = sub_data["properties"]
            sub_name = f"S{k}C{i}"
            sub_file = Path(sub_artifacts["cdsl"])
            sub2files[sub_name]["cdsl"] = sub_file
            sub_encoded_file = Path(sub_artifacts["cdsl_encoded"]) if "cdsl_encoded" in sub_artifacts else None
            sub_properties = sub_data["properties"]
            if cfu_encoder is not None:
                validate_candidate(sub_properties)
            instr_name = sub_properties["InstrName"]
            if sub_encoded_file is not None:
                sub2files[sub_name]["cdsl_encoded"] = sub_encoded_file
            set_instr2sub_name[(set_name, instr_name)] = sub_name
            generated_sets.append((set_name, sub_name, sub_file, sub_encoded_file))
    # Not uses set() here as we want to preserve the order!
    all_cdsl_sets = []
    instr_classes = {32}
    compressed = "c" in base_extensions
    instr_classes.add(16)
    for ext in base_extensions:
        if ext == "c":
            continue
        cdsl_sets = get_cdsl_sets(ext, xlen=xlen, compressed=compressed)
        for cdsl_set in cdsl_sets:
            if cdsl_set not in all_cdsl_sets:
                all_cdsl_sets.append(cdsl_set)
    if not ignore_etiss:
        all_cdsl_sets = apply_etiss_overrides(all_cdsl_sets, semihosting=semihosting)
    # print("all_cdsl_sets", all_cdsl_sets)
    core_includes = get_cdsl_includes(all_cdsl_sets, base_dir=base_dir, tum_dir=tum_dir)
    for set_name in set_names:
        set_out_cdsl_file = gen_dir / f"{set_name}.core_desc"
        core_includes.add(set_out_cdsl_file.resolve())
    # print("cdsl_includes", cdsl_includes)
    core_includes_code = get_includes_code(core_includes)
    constants = {}
    memories = {}
    constants["XLEN"] = m2isar.metamodel.arch.Constant("XLEN", value=xlen, attributes={}, size=None, signed=False)
    # if ignore_etiss:
    if True:
        main_reg = m2isar.metamodel.arch.Memory(
            "X",
            m2isar.metamodel.arch.RangeSpec(32),
            size=xlen,
            attributes={m2isar.metamodel.arch.MemoryAttribute.IS_MAIN_REG: []},
        )
        main_mem = m2isar.metamodel.arch.Memory(
            "MEM",
            m2isar.metamodel.arch.RangeSpec(1 << 32),
            size=8,
            attributes={m2isar.metamodel.arch.MemoryAttribute.IS_MAIN_MEM: []},
        )
        pc = m2isar.metamodel.arch.Memory(
            "PC",
            m2isar.metamodel.arch.RangeSpec(0),
            size=32,
            attributes={m2isar.metamodel.arch.MemoryAttribute.IS_PC: []},
        )
        memories["X"] = main_reg
        memories["MEM"] = main_mem
        memories["PC"] = pc
    functions = {}
    intrinsics = {}
    contributing_types = all_cdsl_sets
    if extra_includes is None:
        extra_includes = []
    # extra_includes = ["/work/git/students/cecil/etiss_arch_riscv/rv_base"]  # TODO: Do not hardcode
    # extra_includes = ["/mnt/wd8tb/Data/students_archive/cecil/etiss_arch_riscv/rv_base"]  # TODO: Do not hardcode
    # print("SSSS")
    # name_idx = 0
    errs_file = gen_dir / "errs.txt"
    errs = {}
    unencoded_instructions_per_set = defaultdict(dict)
    instructions_per_set = defaultdict(dict)
    with ProcessPoolExecutor(n_parallel) as pool:

        futures = []
        for set_name, set_name_, set_file, set_encoded_file in generated_sets:
            if auto_encoding:
                set_file_ = set_file
            else:
                assert set_encoded_file is not None, "cdsl_encoded artifact not found with auto_encoding disabled"
                set_file_ = set_encoded_file
            future = pool.submit(
                parse_generated_set,
                set_file_,
                set_name=set_name,
                skip_errors=skip_errors,
                extra_includes=extra_includes,
                add_mnemonic_prefix=add_mnemonic_prefix,
                auto_encoding=auto_encoding,
            )
            futures.append(future)
        for future, (_, candidate_name, _, _) in zip(futures, generated_sets):
            # TODO: except failing?
            result = future.result()
            parsed_instructions, set_name, err_msg = result
            if parsed_instructions is None:
                assert err_msg is not None
                errs[(set_name, candidate_name)] = err_msg
                continue
            # assert set_name not in unencoded_instructions_per_set, f"Duplicate set name: {set_name}"
            target = unencoded_instructions_per_set if auto_encoding else instructions_per_set
            duplicates = set(target[set_name]) & set(parsed_instructions)
            if duplicates:
                raise EncodingError(f"{set_name}: duplicate instruction names: {sorted(duplicates)}")
            target[set_name].update(parsed_instructions)

    if auto_encoding and cfu_encoder is None:
        manifest = None
        if encoding_manifest is not None:
            manifest = json.loads(Path(encoding_manifest).read_text())
        policy = EncodingPolicy(
            opcodes=tuple(encoding_opcodes) if encoding_opcodes is not None else EncodingPolicy().opcodes,
            reservations=tuple(encoding_reservations),
        )
        instructions_per_set, encoding_plan = encode_instruction_sets(
            unencoded_instructions_per_set,
            existing_per_set=instructions_per_set,
            policy=policy,
            assignments=manifest,
        )
        logger.info("Planned %d encodings across %d sets", len(encoding_plan.assignments), len(instructions_per_set))
    elif auto_encoding:
        pending_encoded = {}
        for set_name, pending in sorted(unencoded_instructions_per_set.items()):
            pending_encoded[set_name] = []
            for instr in sorted(pending.values(), key=lambda instruction: instruction.name):
                sub_name = set_instr2sub_name[(set_name, instr.name)]
                pending_encoded[set_name].append(
                    cfu_encoder.encode(instr, set_name, sub2files[sub_name]["cdsl"])
                )
        validate_instruction_sets(pending_encoded)
        instructions_per_set = {
            name: {(instr.code, instr.mask): instr for instr in instructions}
            for name, instructions in pending_encoded.items()
        }
    # Validate manual encodings too, before any dictionary or core output hides a collision.
    validate_instruction_sets(instructions_per_set)
    for set_name in instructions_per_set.keys():
        contributing_types.append(set_name)
    # instructions = {}
    # instructions.update(encoded_instructions)
    # input("1")
    generated_core = m2isar.metamodel.arch.CoreDef(
        name=core_name,
        contributing_types=contributing_types,
        template=None,  # type: ignore
        constants=constants,
        memories=memories,
        memory_aliases={},
        functions=functions,
        # instructions=instructions,
        instructions={},
        unencoded_instructions={},
        instr_classes=instr_classes,
        intrinsics=intrinsics,
    )
    # print("generated_core", generated_core)
    with open(core_out_model_file, "wb") as f:
        cores = {core_name: generated_core}
        model_obj = M2Model(M2_METAMODEL_VERSION, cores, {}, {})
        pickle.dump(model_obj, f)
    core_cdsl_code = gen_cdsl_code(model_obj, with_includes=False)
    with open(core_out_cdsl_file, "w") as f:
        f.write(core_includes_code)
        f.write("\n\n")
        f.write(core_cdsl_code)
    extension = [f"RV{xlen}I"]  # TODO: add include?
    set_includes = get_cdsl_includes(extension, base_dir=base_dir, tum_dir=tum_dir)
    set_includes_code = get_includes_code(set_includes)
    set_hls_includes = []  # TODO: fix duplicate includes
    set_hls_includes_code = get_includes_code(set_hls_includes)
    for set_name, instructions in instructions_per_set.items():
        set_out_model_file = gen_dir / f"{set_name}.m2isarmodel"
        set_splitted_out_model_file = gen_dir / f"{set_name}.splitted.m2isarmodel"
        set_out_cdsl_file = gen_dir / f"{set_name}.core_desc"
        set_hls_out_cdsl_file = gen_dir / f"{set_name}.hls.core_desc"
        set_splitted_out_cdsl_file = gen_dir / f"{set_name}.splitted.core_desc"
        generated_set = m2isar.metamodel.arch.InstructionSet(
            name=set_name,
            extension=extension,
            constants={},
            memories={},
            functions={},
            instructions=instructions_per_set[set_name],
            unencoded_instructions={},
        )
        # print("generated_set", generated_set)
        with open(set_out_model_file, "wb") as f:
            sets = {set_name: generated_set}
            model_obj = M2Model(M2_METAMODEL_VERSION, {}, sets, {})
            pickle.dump(model_obj, f)
        set_cdsl_code = gen_cdsl_code(model_obj, with_includes=False)
        with open(set_out_cdsl_file, "w") as f:
            f.write(set_includes_code)
            f.write("\n\n")
            f.write(set_cdsl_code)
        sets_splitted = {}
        for instr_def in generated_set.instructions.values():
            instr_name = instr_def.name
            temp_set_name = f"{set_name}{instr_name}single"
            temp_set = m2isar.metamodel.arch.InstructionSet(
                name=temp_set_name,
                extension=extension,
                constants={},
                memories={},
                functions={},
                instructions={(instr_def.code, instr_def.mask): instr_def},
                unencoded_instructions={},
            )
            sets_splitted[temp_set_name] = temp_set
            if auto_encoding:
                model_obj_single = M2Model(M2_METAMODEL_VERSION, {}, {temp_set_name: temp_set}, {})
                sub_name = set_instr2sub_name[(set_name, instr_name)]
                sub_files = sub2files[sub_name]
                base_cdsl_file = str(sub_files["cdsl"])
                base_cdsl_file_encoded = base_cdsl_file.replace(".core_desc", ".encoded.core_desc")
                set_single_out_model_file = base_cdsl_file_encoded.replace(".core_desc", ".m2isarmodel")
                set_single_out_cdsl_file = base_cdsl_file_encoded
                with open(set_single_out_model_file, "wb") as f:
                    pickle.dump(model_obj_single, f)
                extension2 = [f"RV{xlen}I"]  # TODO: add include?
                set_includes2 = get_cdsl_includes(extension2, base_dir=base_dir, tum_dir=tum_dir)
                set_includes_code2 = get_includes_code(set_includes2)
                set_single_cdsl_code = gen_cdsl_code(model_obj_single, with_includes=False)
                with open(set_single_out_cdsl_file, "w") as f:
                    f.write(set_includes_code2)
                    f.write("\n\n")
                    f.write(set_single_cdsl_code)
                sub2new_files[sub_name]["cdsl_encoded"] = base_cdsl_file_encoded
        group_set = m2isar.metamodel.arch.InstructionSet(
            name=set_name,
            extension=list(sets_splitted.keys()),
            constants={},
            memories={},
            functions={},
            instructions={},
            unencoded_instructions={},
        )
        sets_splitted[set_name] = group_set
        model_obj_splitted = M2Model(M2_METAMODEL_VERSION, {}, sets_splitted, {})
        with open(set_splitted_out_model_file, "wb") as f:
            pickle.dump(model_obj_splitted, f)
        set_splitted_cdsl_code = gen_cdsl_code(model_obj_splitted, with_includes=False)
        with open(set_splitted_out_cdsl_file, "w") as f:
            f.write(set_includes_code)
            f.write("\n\n")
            f.write(set_splitted_cdsl_code)
        model_obj.sets[set_name].memories["X"] = main_reg
        model_obj.sets[set_name].extension = []
        hls_unique_instr_names = len(set_names) > 1
        if hls_unique_instr_names:
            assert add_mnemonic_prefix
            for instr_def in model_obj.sets[set_name].instructions.values():
                instr_def.name = instr_def.mnemonic.upper().replace(".", "_")
        set_hls_cdsl_code = gen_cdsl_code(model_obj, with_includes=False, legacy=True)
        with open(set_hls_out_cdsl_file, "w") as f:
            f.write(set_hls_includes_code)
            f.write("\n\n")
            f.write(set_hls_cdsl_code)
        if len(errs) > 0:
            with open(errs_file, "w") as f:
                errs_text = "\n".join([f"{name}: {err}" for name, err in errs.items()])
                f.write(errs_text)
    if auto_encoding:
        for combined_index_file, index_data, k in index_records:
            for i, candidate in enumerate(index_data["candidates"]):
                new_artifacts = sub2new_files.get(f"S{k}C{i}")
                if new_artifacts:
                    candidate["artifacts"].update(new_artifacts)
            with open(combined_index_file, "w") as f:
                yaml.dump(index_data, f)
    if encoding_plan is not None:
        (gen_dir / "encoding_plan.json").write_text(json.dumps(encoding_plan.to_dict(), indent=2) + "\n")
    if cfu_encoder is not None:
        cfu_encoder.save()
        # Keep an exact snapshot with each generated core for provenance.
        snapshot = gen_dir / "cfu_manifest.json"
        snapshot.write_text(cfu_encoder.path.read_text())


def handle(args):
    # assert args.session is not None
    sess = None
    if args.session is not None:
        from isaac_toolkit.session import Session

        session_dir = Path(args.session)
        assert session_dir.is_dir(), f"Session dir does not exist: {session_dir}"
        sess = Session.from_dir(session_dir)
    set_log_level(console_level=args.log, file_level=args.log)
    generate_etiss_core(
        sess,
        force=args.force,
        workdir=args.workdir,
        gen_dir=args.gen_dir,
        index_files=args.index.split(";") if args.index is not None else None,
        core_name=args.core_name,
        set_names=args.set_name.split(";"),
        xlen=args.xlen,
        ignore_etiss=args.ignore_etiss,
        semihosting=args.semihosting,
        base_extensions=args.base_extensions.split(","),
        auto_encoding=args.auto_encoding,
        split=args.split,
        base_dir=args.base_dir,
        tum_dir=args.tum_dir,
        skip_errors=args.skip_errors,
        extra_includes=(args.extra_includes.split(";") if args.extra_includes is not None else None),
        add_mnemonic_prefix=args.add_mnemonic_prefix,
        n_parallel=args.parallel,
        encoding_policy=args.encoding_policy,
        encoding_manifest=args.encoding_manifest,
        encoding_opcodes=args.encoding_opcode,
        encoding_reservations=args.encoding_reserve,
    )
    if sess is not None:
        sess.save()


def parse_reservation(value):
    try:
        code, mask = (int(part, 0) for part in value.split("/"))
        validate_pattern(code, mask)
        return code, mask
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("expected a valid 32-bit CODE/MASK pattern") from exc


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log",
        default="info",
        choices=["critical", "error", "warning", "info", "debug"],
    )  # TODO: move to defaults
    # parser.add_argument("--session", "--sess", "-s", type=str, required=True)
    parser.add_argument("--session", "--sess", "-s", type=str, required=False)
    parser.add_argument("--force", "-f", action="store_true")
    parser.add_argument("--workdir", type=str, default=None)
    parser.add_argument("--gen-dir", type=str, default=None)
    parser.add_argument("--index", type=str, default=None)
    parser.add_argument("--core-name", type=str, default="IsaacCore")
    parser.add_argument("--set-name", type=str, default="XIsaac")
    parser.add_argument("--xlen", type=int, default=32)
    parser.add_argument("--ignore_etiss", action="store_true")
    parser.add_argument("--semihosting", action="store_true")
    parser.add_argument("--base-extensions", type=str, default="i,m,a,f,d,c,zifencei")
    parser.add_argument("--auto-encoding", action="store_true", default=True)
    parser.add_argument("--encoding-policy", choices=["auto", "cfu"], default="auto")
    parser.add_argument("--encoding-manifest", type=str, default=None,
                        help="Auto: input planner manifest; CFU: persistent CFU ledger")
    parser.add_argument("--encoding-opcode", action="append", type=lambda value: int(value, 0),
                        help="Permitted custom major opcode, repeatable (auto policy)")
    parser.add_argument("--encoding-reserve", action="append", default=[], type=parse_reservation,
                        metavar="CODE/MASK", help="Reserved pattern, repeatable (auto policy)")
    parser.add_argument("--no-auto-encoding", dest="auto_encoding", action="store_false", default=True)
    parser.add_argument("--split", action="store_true")
    parser.add_argument("--base-dir", type=str, default="rv_base")
    parser.add_argument("--tum-dir", type=str, default=".")
    parser.add_argument("--parallel", type=int, default=multiprocessing.cpu_count())
    parser.add_argument("--extra-includes", type=str, default=None)  # semicolon separated
    parser.add_argument("--skip-errors", action="store_true")
    parser.add_argument("--add-mnemonic-prefix", action="store_true")

    return parser


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    handle(args)


if __name__ == "__main__":
    main(sys.argv[1:])
