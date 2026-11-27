"""Issue #143: execute both translation stages of coverage-instrumented loops."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from m2isar.metamodel import load_model, behav
from m2isar.metamodel.utils.expr_preprocessor import process_instructions
from m2isar.transforms.lower_loops import lower_loops
from m2isar.transforms.merge_always_blocks import merge_always_blocks
from m2isar.backends.etiss.instruction_transform import InstructionTransformVisitor
from m2isar.backends.etiss.instruction_utils import TransformerContext

FIXTURES = Path(__file__).parent / 'fixtures' / 'etiss_loop_coverage'
TYPES = '#include <cstdint>\n' + ''.join(
    f'using etiss_{kind}{bits} = {kind}{bits}_t;\n'
    for kind in ('int', 'uint') for bits in (8, 16, 32, 64))


class LoopCoverageTests(unittest.TestCase):
    def run_checked(self, args, cwd, timeout=30):
        result = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True,
                                text=True, timeout=timeout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def parse(self, root, body=None):
        text = (FIXTURES / 'LoopCoverage.core_desc').read_text()
        if body:
            start = text.index('                for (int i')
            end = text.index('\n            }', start)
            text = text[:start] + body + text[end:]
        source = root / 'LoopCoverage.core_desc'
        source.write_text(text)
        self.run_checked([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', source], Path.cwd())
        saved = root / 'gen_model' / 'LoopCoverage.m2isarmodel'
        return load_model(saved), saved

    @unittest.skipUnless(shutil.which('g++'), 'g++ required for two-stage execution')
    def test_translator_and_emitted_loop_execute_with_and_without_coverage(self):
        # The first case is the reported static iterator with runtime slices.
        # Others guard runtime loop control, continue, nesting and post-tests.
        cases = [
            (None, 70),
            ('for(int i=0;i<32;i+=8){if(i==8)continue;'
             'X[rd]+=(unsigned<32>)X[rs1][i+7:i]*(unsigned<32>)X[rs2][i+7:i];}', 58),
            ('for(int i=0;i<4;i+=1){if(X[rs1]==0)continue;X[rd]+=1;}', 4),
            ('for(int i=0;i<4;i+=1){if(i==2)break;X[rd]+=1;}', 2),
            ('for(int i=0;i<4;i+=1)X[rd]+=1;', 4),
            ('for(int i=0;i<4;i+=1){for(int j=0;j<2;j+=1){X[rd]+=1;}}', 8),
            ('int i=0;do{X[rd]+=1;i+=1;}while(i<4);', 4),
            ('int i=0;while(i<4){X[rd]+=1;i+=1;}', 4),
        ]
        for body, expected in cases:
            for coverage in (False, True):
                with self.subTest(body=body, coverage=coverage), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    model, _ = self.parse(root, body)
                    source_instruction = next(i for i in model.cores['LoopCoverage'].instructions.values()
                                              if i.name == 'DOTP')
                    loop = source_instruction.operation.statements[0].statements[1]
                    counters = ''
                    if coverage and body is None:
                        counters = (f' && counts[{loop.cond.line_info.id}]==5'
                                    f' && counts[{loop.body.line_info.id}]==4')
                    merge_always_blocks(model)
                    lower_loops(model)
                    core = model.cores['LoopCoverage']
                    process_instructions(core)
                    instruction = next(i for i in core.instructions.values() if i.name == 'DOTP')
                    context = TransformerContext(core.parameters, core.memories, core.memory_aliases,
                        core.register_banks, core.register_aliases, instruction.fields,
                        instruction.attributes, core.functions, 32, 32, core.name, True,
                        core.intrinsics, coverage)
                    output = InstructionTransformVisitor().generate(instruction.operation, context)
                    output.format(ARCH_NAME=core.name)
                    translator = root / 'translator.cpp'
                    translator.write_text(TYPES + '''
#include <iostream>
#include <string>
struct Part { std::string text; std::string& code(){return text;} };
int main(){Part cp;struct {uint64_t current_address_=0;} ic;
unsigned rd=3,rs1=1,rs2=2;
''' + output.initial_required + '\nstd::cout << cp.text;}')
                    self.run_checked(['g++', '-std=c++14', translator, '-o', root / 'translator'], root)
                    emitted = self.run_checked([root / 'translator'], root, timeout=3)
                    # Counters execute in the emitted code, rather than in the translator.
                    runtime = root / 'runtime.cpp'
                    runtime.write_text(TYPES + '''
#include <cstdarg>
#include <map>
std::map<int,int> counts;
void etiss_coverage_count(int n,...){va_list args;va_start(args,n);
while(n--)++counts[va_arg(args,int)];va_end(args);}
struct LoopCoverage{uint32_t X[32]={};uint64_t instructionPointer=0,nextPc=0;};
int main(){LoopCoverage state;auto cpu=&state;
state.X[1]=0x04030201;state.X[2]=0x08070605;
''' + emitted + f'\nreturn state.X[3]=={expected}{counters} ? 0:1;}}')
                    self.run_checked(['g++', '-std=c++14', runtime, '-o', root / 'runtime'], root)
                    self.run_checked([root / 'runtime'], root, timeout=3)

    @unittest.skipUnless(os.environ.get('ETISS_PREFIX'), 'Set ETISS_PREFIX for full architecture/software simulation')
    def test_generated_architecture_software_simulation(self):
        prefix = Path(os.environ['ETISS_PREFIX']).resolve()
        config = next(prefix.glob('lib/[Cc][Mm]ake/ETISS/ETISSConfig.cmake'))
        for coverage in (False, True):
            with self.subTest(coverage=coverage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                model, saved = self.parse(root)
                self.run_checked([sys.executable, '-m', 'm2isar.backends.etiss.writer', saved,
                    '--fill-mode', 'auto', '--coverage' if coverage else '--no-coverage'], Path.cwd())
                (root / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.16)
project(LoopCoverageSimulation LANGUAGES C CXX)
add_subdirectory(gen_output/LoopCoverage/LoopCoverage)
find_package(ETISS REQUIRED)
add_executable(sim sim.cpp)
target_include_directories(sim PRIVATE ${ETISS_INCLUDE_DIRS} gen_output/LoopCoverage/LoopCoverage)
target_link_libraries(sim PRIVATE ${ETISS_LIBRARIES})
''')
                shutil.copyfile(FIXTURES / 'sim.cpp', root / 'sim.cpp')
                self.run_checked(['cmake', '-S', root, '-B', root / 'build',
                    f'-DETISS_DIR={config.parent}', f'-DCMAKE_INSTALL_PREFIX={root / "install"}'], root)
                self.run_checked(['cmake', '--build', root / 'build', '-j2'], root, timeout=120)
                self.run_checked(['cmake', '--install', root / 'build'], root)
                output = self.run_checked([root / 'build/sim', root / 'install/lib/plugins'], root, timeout=15)
                self.assertIn('X[3]=70 X[4]=70 PC=8', output)
                if coverage:
                    report = root / 'coverage.csv'
                    self.assertTrue(report.exists(), 'ETISS must be built with ETISS_USE_COREDSL_COVERAGE=ON')
                    counts = {int(k): int(v) for k, v in
                              (line.split(';') for line in report.read_text().splitlines()[2:])}
                    operation = next(i for i in model.cores['LoopCoverage'].instructions.values()
                                     if i.name == 'DOTP').operation
                    loop = operation.statements[0].statements[1]
                    self.assertIsInstance(loop, behav.ForLoop)
                    self.assertEqual(counts[loop.cond.line_info.id], 10)
                    self.assertEqual(counts[loop.body.line_info.id], 8)
