// SPDX-License-Identifier: Apache-2.0
// Compiled against real Spike headers and libraries by the integration test.
#include "extension.cc"
#include "cfg.h"
#include <cassert>
#include <iostream>

int main() {
  cfg_t cfg;
  const char* isa = m2_Example::xlen == 32 ? "RV32IM" : "RV64IM";
  processor_t first(isa, "M", &cfg, nullptr, 0, false, nullptr, std::cerr);
  processor_t second(isa, "M", &cfg, nullptr, 1, false, nullptr, std::cerr);
  auto factory = find_extension("m2_Example");
  auto* a = static_cast<m2_Example*>(factory());
  auto* b = static_cast<m2_Example*>(factory());
  first.register_extension(a);
  second.register_extension(b);
  assert(a != b);
  assert(a->m2_ACC[0] == 0 && b->m2_ACC[0] == 0);
  first.get_state()->XPR.write(1, 17);
  // Execute state-set through the descriptor selected by Spike.
  auto instructions = a->get_instructions(first);
  auto set = instructions.at(5).func(m2_Example::xlen, false, false);
  set(&first, insn_t((5 << 25) | (1 << 15) | 0xb), 0x80000000);
  assert(a->m2_ACC[0] == 17 && b->m2_ACC[0] == 0);
  assert(a->m2_ACC[1] == 9);
  a->m2_ACC[1] = 123;
  first.reset();
  assert(a->m2_ACC[0] == 0 && a->m2_ACC[1] == 9);
  first.enable_log_commits();
  a->write_x(&first, 3, UINT64_MAX);
  assert(first.get_state()->XPR[3] == reg_t(-1));
  assert(first.get_state()->log_reg_write.at(3 << 4).v[0] == reg_t(-1));
  processor_t wide(m2_Example::xlen == 32 ? "RV64IM" : "RV32IM", "M", &cfg, nullptr, 2, false, nullptr, std::cerr);
  bool wrong_xlen = false;
  try { set(&wide, insn_t(0xb), 0x80000000); }
  catch (const trap_illegal_instruction&) { wrong_xlen = true; }
  assert(wrong_xlen);
  assert(set(&first, insn_t((5 << 25) | (1 << 15) | 0xb), 0xfffffffffffffffcULL)
         == 0);
  if (m2_Example::xlen == 64) {
    first.get_state()->XPR.write(1, 0xfedcba9876543210ULL);
    set(&first, insn_t((5 << 25) | (1 << 15) | 0xb), 0x100000000ULL);
    assert(a->m2_ACC[0] == 0xfedcba9876543210ULL);
    auto get = instructions.at(6).func(64, false, true);
    assert(get(&first, insn_t((6 << 25) | (3 << 7) | 0xb), 0x100000000ULL)
           == 0x100000004ULL);
    assert(first.get_state()->XPR[3] == 0xfedcba9876543210ULL);
    assert(first.get_state()->log_reg_write.at(3 << 4).v[0] == 0xfedcba9876543210ULL);
    first.reset();
    assert(a->m2_ACC[0] == 0 && a->m2_ACC[1] == 9);
  }
  bool trapped = false;
  try { a->state_at(a->m2_ACC, 4, insn_t(0xb)); }
  catch (const trap_illegal_instruction&) { trapped = true; }
  assert(trapped);
}
