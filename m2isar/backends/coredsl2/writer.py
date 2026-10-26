# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Clean M2-ISA-R/Seal5 metamodel to .core_desc file."""

import copy
import argparse
import logging
import pathlib


from ...metamodel import load_model
from .utils import CoreDSL2Writer
from .visitor import CDSLWriterVisitor
from ...metrics import add_metrics_args, init_metrics, handle_metrics
from ...logging import add_logging_args, handle_logging_args
from ...iter_utils import process_sets, process_cores, process_sets_instructions, process_cores_instructions

logger = logging.getLogger("coredsl2_writer")


def write_cdsl_splitted(model_obj, out_path, ext: str = "core_desc", metrics=None, writer_cls=None, writer_kwargs=None):
    model_obj = copy.deepcopy(model_obj)
    # The instruction iterators operate on one collection; include pending
    # instructions so --splitted cannot silently omit auto encodings.
    for container in [*model_obj.sets.values(), *model_obj.cores.values()]:
        container.instructions = dict(container.instructions)
        container.instructions.update(container.unencoded_instructions)
        container.unencoded_instructions = {}
    assert out_path is not None
    out_path = pathlib.Path(out_path)
    assert out_path.is_dir(), "Expecting output directory when using --splitted"
    num_cores = len(model_obj.cores)
    num_sets = len(model_obj.sets)
    visitor = CDSLWriterVisitor()
    if writer_cls is None:
        writer_cls = CoreDSL2Writer
    if writer_kwargs is None:
        writer_kwargs = {}
    if num_sets > 0:

        def _helper(set_def, instr_def):
            writer = writer_cls(visitor, drop_first_op=False, **writer_kwargs)
            set_def_ = copy.deepcopy(set_def)
            set_def_.instructions = {
                key: instr_def_ for key, instr_def_ in set_def.instructions.items() if instr_def.name == instr_def_.name
            }
            writer.write_set(set_def_)
            content = writer.text
            set_name = set_def.name
            out_path_ = out_path / set_name / f"{instr_def.name}.{ext}"
            out_path_.parent.mkdir(exist_ok=True)
            with open(out_path_, "w", encoding="utf-8") as f:
                f.write(content)

        process_sets_instructions(model_obj, _helper, description="Writing CoreDSL2", metrics=metrics)
    if num_cores > 0:

        def _helper(core_def, instr_def):
            writer = writer_cls(visitor, drop_first_op=False, **writer_kwargs)
            core_def_ = copy.deepcopy(core_def)
            core_def_.instructions = {
                key: instr_def_
                for key, instr_def_ in core_def.instructions.items()
                if instr_def.name == instr_def_.name
            }
            writer.write_core(core_def_)
            content = writer.text
            core_name = core_def.name
            out_path_ = out_path / core_name / f"{instr_def.name}.{ext}"
            out_path_.parent.mkdir(exist_ok=True)
            with open(out_path_, "w", encoding="utf-8") as f:
                f.write(content)

        process_cores_instructions(model_obj, _helper, description="Writing CoreDSL2", metrics=metrics)
    return metrics


def write_cdsl_default(model_obj, out_path, metrics=None, writer_cls=None, writer_kwargs=None):
    num_cores = len(model_obj.cores)
    num_sets = len(model_obj.sets)
    visitor = CDSLWriterVisitor()
    if writer_cls is None:
        writer_cls = CoreDSL2Writer
    if writer_kwargs is None:
        writer_kwargs = {}
    writer = writer_cls(visitor, drop_first_op=False, **writer_kwargs)
    if num_sets > 0:

        def _helper(set_def):
            writer.write_set(set_def)

        process_sets(model_obj, _helper, description="Writing CoreDSL2", metrics=metrics)
    if num_cores > 0:

        def _helper(core_def):
            writer.write_core(core_def)

        process_cores(model_obj, _helper, description="Writing CoreDSL2", metrics=metrics)
    content = writer.text
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return metrics


def write_includes(writer, used_extensions, includes_prefix: str = "rv_base/", tum_includes_prefix: str = ""):
    if {"RV32I", "RV64I"}.intersection(used_extensions):
        writer.write(f'import "{includes_prefix}RVI.core_desc"', nl=True)
    if "RV32M" in used_extensions or "RV64M" in used_extensions:
        writer.write(f'import "{includes_prefix}RVM.core_desc"', nl=True)
    if "RV32IC" in used_extensions or "RV64IC" in used_extensions:
        writer.write(f'import "{includes_prefix}RVC.core_desc"', nl=True)
    if "RV32F" in used_extensions or "RV64F" in used_extensions:
        writer.write(f'import "{includes_prefix}RVF.core_desc"', nl=True)
    if "RV32D" in used_extensions or "RV64D" in used_extensions:
        writer.write(f'import "{includes_prefix}RVD.core_desc"', nl=True)

    # add tum extensions at the end
    if "tum_csr" in used_extensions:
        writer.write(f'import "{tum_includes_prefix}tum_mod.core_desc"', nl=True)
        writer.write(f'import "{tum_includes_prefix}tum_rva.core_desc"', nl=True)
        writer.write(f'import "{tum_includes_prefix}tum_rvm.core_desc"', nl=True)
    writer.write("\n")


def gen_cdsl_code(model_obj, with_includes=True, includes_prefix="rv_base/", tum_includes_prefix="", legacy=False):
    """Generate CoreDSL without modifying the caller's model or behavior."""
    model_obj = copy.deepcopy(model_obj)
    writer = CoreDSL2Writer(CDSLWriterVisitor(), reduced=False, legacy=legacy)
    if with_includes:
        extensions = set()
        for core in model_obj.cores.values():
            extensions.update(core.contributing_types)
        for instruction_set in model_obj.sets.values():
            extensions.update(instruction_set.extension)
        write_includes(writer, extensions, includes_prefix, tum_includes_prefix)
    for instruction_set in model_obj.sets.values():
        writer.write_set(instruction_set)
    for core in model_obj.cores.values():
        writer.write_core(core)
    return writer.text



def main(argv=None):
    """Main app entrypoint."""

    # read command line args
    parser = argparse.ArgumentParser()
    parser.add_argument("top_level", help="A .m2isarmodel or .seal5model file.")
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--reduced", action="store_true", help="Generate pattern-gen compatible syntax")
    parser.add_argument("--splitted", action="store_true", help="Split per set and instruction")
    parser.add_argument("--ext", type=str, default="core_desc", help="Default file extension (if using --splitted)")
    parser.add_argument("--legacy", action="store_true", help="Emit legacy assembly syntax")
    add_logging_args(parser)
    add_metrics_args(parser)
    args = parser.parse_args(argv)

    handle_logging_args(args)

    # resolve model paths
    top_level = pathlib.Path(args.top_level)
    if args.output is None:
        out_path = f"{top_level}.{args.ext}"
    else:
        out_path = pathlib.Path(args.output)

    # load models
    model_obj = load_model(top_level)

    allowed_attrs = None  # all
    metrics = init_metrics()
    writer_kwargs = dict(reduced=args.reduced, allowed_attrs=allowed_attrs, legacy=args.legacy)
    if args.splitted:
        metrics = write_cdsl_splitted(
            model_obj, out_path=out_path, ext=args.ext, metrics=metrics, writer_kwargs=writer_kwargs
        )
    else:
        metrics = write_cdsl_default(model_obj, out_path=out_path, metrics=metrics, writer_kwargs=writer_kwargs)

    handle_metrics(metrics, dest=args.metrics, ignore_failing=args.ignore_failing)


if __name__ == "__main__":
    main()
