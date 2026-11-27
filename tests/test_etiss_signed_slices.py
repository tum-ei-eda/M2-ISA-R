"""Issue #144: indexed slices retain their width through signedness casts."""
from pathlib import Path
import shutil
import tempfile
import unittest

import test_etiss_loop_coverage as harness
from m2isar.backends.etiss.instruction_transform import InstructionTransformVisitor
from m2isar.backends.etiss.instruction_utils import TransformerContext
from m2isar.metamodel import arch, behav, type_info, attribute_info as ai
from m2isar.transforms.infer_types.visitor import InferTypesMutator
from m2isar.warnings import WarningsManager


class SignedSliceTests(unittest.TestCase):
    run_checked = harness.LoopCoverageTests.run_checked

    @unittest.skipUnless(shutil.which('g++'), 'g++ required for signed-slice execution')
    def test_indexed_and_constant_slices_have_identical_signed_values(self):
        program = harness.TYPES + '''
using etiss_int128=__int128;using etiss_uint128=unsigned __int128;
int main(){
'''
        for width in (1, 3, 7, 8, 9, 16, 31, 32, 64, 128):
            storage = 32 if width <= 32 else width
            source_type = type_info.PrimitiveType(type_info.TypeKind.UINT, storage)
            value = arch.Variable('value', source_type, attributes={'static': ai.AccessAttribute.NONE})
            index_type = type_info.PrimitiveType(type_info.TypeKind.INT, 32)
            index = arch.Variable('i', index_type, attributes={'static': ai.AccessAttribute.NONE})
            for offset in sorted({0, storage - width}):
                for dynamic in (False, True):
                    lo = behav.NamedReference(index) if dynamic else behav.Literal(offset, index_type)
                    hi = (behav.BinaryOperation(behav.NamedReference(index), behav.Operator('+'),
                          behav.Literal(width - 1, index_type)) if dynamic else behav.Literal(offset + width - 1, index_type))
                    sliced = behav.SliceOperation(behav.NamedReference(value), hi, lo)
                    cast = behav.TypeConv(type_info.TypeKind.INT, None, sliced)
                    InferTypesMutator().generate(cast, WarningsManager(None))
                    context = TransformerContext({}, {}, {}, {}, {}, {}, [], {}, 0,
                        storage, 'C', False, {}, False, ignore_static=True)
                    visitor = InstructionTransformVisitor()
                    generated_slice = visitor.generate(sliced, context)
                    self.assertEqual((generated_slice.size, generated_slice.signed), (width, False))
                    expression = visitor.generate(cast, context)
                    self.assertEqual((expression.size, expression.signed), (width, True))
                    # Check zero, largest positive, minimum negative and -1,
                    # with all bits outside the slice set to catch masking errors.
                    for bits in sorted({0, (1 << (width - 1)) - 1, 1 << (width - 1), (1 << width) - 1}):
                        signed = bits - (1 << width) if bits & (1 << (width - 1)) else bits
                        source = ((1 << storage) - 1) ^ (((1 << width) - 1) << offset) | (bits << offset)
                        literal = (f'((etiss_uint128){source >> 64}ULL<<64)|{source & ((1<<64)-1)}ULL'
                                   if storage == 128 else f'{source}ULL')
                        expected_bits = signed & ((1 << 128) - 1)
                        expected = (f'((etiss_int128)(((etiss_uint128){expected_bits >> 64}ULL<<64)'
                                    f'|{expected_bits & ((1<<64)-1)}ULL))')
                        program += (f'{{etiss_uint{storage} value={literal};int i={offset};'
                                    f'if(({expression.code})!=({expected}))return 1;}}\n')
        program += 'return 0;}'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'slice.cpp').write_text(program)
            self.run_checked(['g++', '-std=c++14', root / 'slice.cpp', '-o', root / 'slice'], root)
            self.run_checked([root / 'slice'], root)
