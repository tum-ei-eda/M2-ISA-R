# SPDX-License-Identifier: Apache-2.0
"""Write a standalone Spike plugin, without modifying Spike sources."""
from .plugin import generate_plugin


def write_instructions(set_def, start_time, output_path):
    """Write one extension translation unit and its build instructions."""
    output_path.mkdir(parents=True, exist_ok=True)
    source = generate_plugin(set_def)
    (output_path / "extension.cc").write_text(source, encoding="utf-8")
    (output_path / "Makefile").write_text(
        "CXX ?= c++\n"
        "CPPFLAGS += -I$(SPIKE_INCLUDE)\n"
        "CXXFLAGS += -std=c++17 -fPIC\n"
        "all: libextension.so\n"
        "libextension.so: extension.cc\n"
        "\t$(CXX) $(CPPFLAGS) $(CXXFLAGS) -shared $< -o $@\n",
        encoding="utf-8",
    )
