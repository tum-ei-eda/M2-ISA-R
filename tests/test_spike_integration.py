"""Opt-in execution against a real Spike build (no stub headers)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('SPIKE_SOURCE') and os.environ.get('SPIKE_BUILD'),
                     'set SPIKE_SOURCE and SPIKE_BUILD to run real Spike integration')
class SpikeIntegration(unittest.TestCase):
    def test_rv32_shared_plugin_guest_execution(self):
        self.run_guest(32)

    def test_rv64_shared_plugin_guest_execution(self):
        self.run_guest(64)

    def run_guest(self, xlen):
        source = Path(os.environ['SPIKE_SOURCE']).resolve()
        build = Path(os.environ['SPIKE_BUILD']).resolve()
        spike = Path(os.environ.get('SPIKE_BIN', str(build / 'spike')))
        self.assertIsNotNone(shutil.which('clang'), 'clang with RISC-V target required')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            model = (Path(__file__).parent / 'fixtures' / 'spike.core_desc').read_text()
            (output / 'spike.core_desc').write_text(model.replace('unsigned<32>', f'unsigned<{xlen}>'))
            subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser',
                            str(output / 'spike.core_desc')], check=True, capture_output=True, timeout=30)
            subprocess.run([sys.executable, '-m', 'm2isar.backends.spike.writer',
                            str(output / 'gen_model' / 'spike.m2isarmodel')],
                           check=True, capture_output=True, timeout=30)
            shutil.copy(output / 'gen_output' / 'spike' / 'Example' / 'extension.cc', output)
            includes = [source, source / 'riscv', source / 'fesvr', source / 'softfloat', build]
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-shared',
                            *[f'-I{p}' for p in includes], str(output / 'extension.cc'),
                            '-o', str(output / 'libextension.so')], check=True, timeout=60)
            shutil.copy(Path(__file__).parent / 'fixtures' / 'spike_state.cc', output)
            subprocess.run(['c++', '-std=c++17', *[f'-I{p}' for p in includes],
                            str(output / 'spike_state.cc'), f'-L{build}',
                            '-Wl,--start-group', '-lriscv', '-ldisasm', '-lfesvr',
                            '-lsoftfloat', '-lfdt', '-Wl,--end-group',
                            '-lpthread', '-ldl', '-lboost_system', '-lboost_regex',
                            '-o', str(output / 'state_test')], check=True, timeout=60)
            subprocess.run([str(output / 'state_test')], check=True, timeout=30)
            def custom(funct, rd=3, rs1=1, rs2=2):
                return f'.word {(funct << 25) | (rs2 << 20) | (rs1 << 15) | (rd << 7) | 0x0b}'
            assembly = ['.section .text', '.global _start', '_start:', 'li x1, 7', 'li x2, 3']
            for funct, expected in enumerate([10, 4, 4, 3, 7]):
                assembly += [custom(funct), f'li x4, {expected}', 'bne x3, x4, fail']
            if xlen == 64:
                assembly += ['li x1, 0x100000007', 'li x2, 3', custom(0),
                             'li x4, 0x10000000a', 'bne x3, x4, fail',
                             custom(5), custom(7), custom(6),
                             'li x4, 0x20000000e', 'bne x3, x4, fail',
                             'li x1, 0x8000000000000000', custom(5), custom(6),
                             'bne x3, x1, fail', 'li x1, 7']
            assembly += [custom(5), custom(6), 'bne x3, x1, fail', custom(7), custom(6),
                         'li x4, 14', 'bne x3, x4, fail', custom(0, rd=0), 'bnez x0, fail',
                         'li x1, -1', 'li x2, 1', custom(0), 'bnez x3, fail',
                         'li x5, 1', 'j finish', 'fail:', 'li x5, 3', 'finish:',
                         'la x6, tohost', 'sw zero, 4(x6)', 'sw x5, 0(x6)', '1: j 1b',
                         '.section .tohost,"aw",@progbits', '.balign 64', '.global tohost',
                         'tohost: .dword 0', '.global fromhost', 'fromhost: .dword 0']
            (output / 'guest.S').write_text('\n'.join(assembly) + '\n')
            (output / 'guest.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x80000000; .text : { *(.text*) } .tohost : { *(.tohost) } }\n')
            subprocess.run(['clang', f'--target=riscv{xlen}', f'-march=rv{xlen}im',
                            '-mabi=' + ('ilp32' if xlen == 32 else 'lp64'),
                            '-nostdlib', '-fuse-ld=lld', f'-Wl,-T,{output / "guest.ld"}',
                            '-Wl,--entry=_start', str(output / 'guest.S'), '-o', str(output / 'guest.elf')],
                           check=True, timeout=60)
            result = subprocess.run([str(spike), f'--isa=RV{xlen}IM',
                                     f'--extlib={output / "libextension.so"}',
                                     '--extension=m2_Example', str(output / 'guest.elf')],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
