#include <etiss/ETISS.h>
#include <etiss/CPUCore.h>
#include <etiss/jit/System.h>
#include <etiss/jit/ReturnCode.h>
#include "LoopCoverage.h"
#include <cstring>
#include <iostream>
static etiss_int32 fetch(void*, etiss_uint64 addr, etiss_uint8* buffer, etiss_uint32 length) {
    const uint32_t program[] = {
        (2u<<20) | (1u<<15) | (3u<<7) | 0x0b, // DOTP X[3], X[1], X[2]
        (2u<<20) | (1u<<15) | (4u<<7) | 0x0b, // DOTP X[4], X[1], X[2]
        0x6b,                               // STOP (jump to self)
    };
    if (addr + length > sizeof(program)) return etiss::RETURNCODE::IBUS_READ_ERROR;
    std::memcpy(buffer, reinterpret_cast<const uint8_t*>(program) + addr, length);
    return 0;
}
static etiss_int32 readi(void*, ETISS_CPU*, etiss_uint64, etiss_uint32) { return 0; }
static etiss_int32 data(void*, ETISS_CPU*, etiss_uint64, etiss_uint8*, etiss_uint32) { return -5; }
static etiss_int32 write(void*, etiss_uint64, etiss_uint8*, etiss_uint32) { return -6; }
static void sync(void*, ETISS_CPU*) {}
int main(int argc, char** argv) {
    etiss::Initializer init(1, argv);
    if (argc < 2 || !etiss::loadLibrary(argv[1], "LoopCoverage")) return 3;
    etiss::cfg().set<std::string>("jit.external_header_paths", std::string(argv[1]) + "/../../include/jit;");
    etiss::cfg().set<bool>("etiss.exit_on_loop", true);
    etiss::cfg().set<int>("etiss.max_block_size", 1);
    auto core = etiss::CPUCore::create("LoopCoverage", "issue143");
    if (!core) return 2;
    core->set(etiss::getJIT("GCCJIT"));
    core->setTimer(false);
    etiss_uint64 start = 0;
    core->reset(&start);
    auto state = reinterpret_cast<LoopCoverage*>(core->getState());
    // Four unsigned byte products: 1*5 + 2*6 + 3*7 + 4*8 = 70.
    state->X[1] = 0x04030201;
    state->X[2] = 0x08070605;
    ETISS_System system = {readi, data, data, data, fetch, write, sync, nullptr};
    std::cout << "Executing DOTP software program" << std::endl;
    auto result = core->execute(system);
    std::cout << "result=" << result << " X[3]=" << state->X[3] << " X[4]=" << state->X[4] << " PC=" << core->getState()->instructionPointer << std::endl;
    return result == etiss::RETURNCODE::CPUFINISHED && state->X[3] == 70 && state->X[4] == 70 && core->getState()->instructionPointer == 8 ? 0 : 1;
}
