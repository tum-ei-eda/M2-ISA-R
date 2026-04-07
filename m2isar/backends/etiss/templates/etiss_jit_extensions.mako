    {
        /* Set default JIT Extensions. Read Parameters set from ETISS configuration and append with architecturally needed */
        std::string cfgPar = "";
        cfgPar = etiss::cfg().get<std::string>("jit.external_headers", ";");
        etiss::cfg().set<std::string>("jit.external_headers", cfgPar + "${extra_headers}");

        cfgPar = etiss::cfg().get<std::string>("jit.external_libs", ";");
        etiss::cfg().set<std::string>("jit.external_libs", cfgPar + "${extra_libs}");

        cfgPar = etiss::cfg().get<std::string>("jit.external_header_paths", ";");
        etiss::cfg().set<std::string>("jit.external_header_paths", cfgPar + "${extra_header_paths}");

        cfgPar = etiss::cfg().get<std::string>("jit.external_lib_paths", ";");
        etiss::cfg().set<std::string>("jit.external_lib_paths", cfgPar + "${extra_lib_paths}");
    }
