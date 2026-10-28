"""Regression checks for absent instruction widths in generated ETISS code."""

from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from mako.template import Template


class InvalidInstructionCallbacksTest(unittest.TestCase):
    def test_generated_registration_handles_missing_widths(self):
        compiler = shutil.which("g++") or shutil.which("clang++")
        if compiler is None:
            self.skipTest("A C++ compiler is required for the generated-code regression")
        template = Path(__file__).resolve().parents[1] / "m2isar/backends/etiss/templates/etiss_arch_specific_cpp.mako"
        generated = Template(filename=str(template)).render(
            start_time="test", core_name="Guard", error_fn=None,
            main_reg=SimpleNamespace(size=32, range=SimpleNamespace(length=32)),
            irq_en_reg=None, irq_pending_reg=None, global_irq_en_reg=None,
            global_irq_en_mask=None,
            error_callbacks={16: "[]() {}", 32: "[]() {}", 64: "[]() {}"},
        )
        start = generated.index("void GuardArch::initInstrSet(")
        end = generated.index("\n/**", start)
        registration = generated[start:end]
        # Compile the actual generated method against the small ETISS API surface
        # it uses, then exercise missing and present sets. No text substitution.
        source = r'''
#include <cassert>
#include <iostream>
#include <map>
#include <string>
namespace etiss {
enum Severity { FATALERROR };
void log(Severity, const char *) { assert(false); }
namespace instr {
struct Invalid {
    unsigned callbacks = 0;
    template<typename Callback> void addCallback(Callback, int) { ++callbacks; }
};
struct InstructionSet {
    Invalid invalid;
    Invalid &getInvalid() { return invalid; }
};
struct VariableInstructionSet {
    std::map<unsigned, InstructionSet> sets;
    std::map<unsigned, unsigned> lookups;
    InstructionSet *get(unsigned width) {
        ++lookups[width];
        auto found = sets.find(width);
        return found == sets.end() ? nullptr : &found->second;
    }
};
struct ModedInstructionSet {
    VariableInstructionSet variable;
    explicit ModedInstructionSet(const char *) {}
    VariableInstructionSet *get(unsigned mode) { assert(mode == 1); return &variable; }
    void compile() {}
    std::string print() { return ""; }
};
}}
struct ISA {
    void addTo(etiss::instr::ModedInstructionSet &, bool &ok) const { ok = true; }
} GuardISA;
struct GuardArch {
    void initInstrSet(etiss::instr::ModedInstructionSet &) const;
};
'''
        source += registration
        source += r'''
int main() {
    for (unsigned available : {2u, 3u, 5u, 7u}) {
        etiss::instr::ModedInstructionSet mis("test");
        unsigned widths[] = {16, 32, 64};
        for (unsigned i = 0; i < 3; ++i)
            if (available & (1u << i)) mis.variable.sets[widths[i]];
        GuardArch().initInstrSet(mis);
        for (unsigned width : widths) {
            assert(mis.variable.lookups[width] == 1);
            auto found = mis.variable.sets.find(width);
            if (found != mis.variable.sets.end()) assert(found->second.invalid.callbacks == 1);
        }
    }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp, executable = Path(directory) / "callbacks.cpp", Path(directory) / "callbacks"
            cpp.write_text(source)
            subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                            str(cpp), "-o", str(executable)], check=True, capture_output=True)
            subprocess.run([str(executable)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
