    {
        std::string requiredJitFilesPath = jitFiles();
        // Keep user entries and add each architecture requirement once, even
        // when execute() initializes the instruction set again.
        auto appendJitEntries = [](const std::string &key, const std::string &entries) {
            std::string value = etiss::cfg().get<std::string>(key, ";");
            std::string::size_type start = 0;
            while (start < entries.size()) {
                auto end = entries.find(';', start);
                std::string entry = entries.substr(start, end == std::string::npos ? end : end - start);
                if (!entry.empty() && (";" + value + ";").find(";" + entry + ";") == std::string::npos) {
                    if (!value.empty() && value.back() != ';')
                        value += ';';
                    value += entry;
                }
                if (end == std::string::npos)
                    break;
                start = end + 1;
            }
            etiss::cfg().set<std::string>(key, value);
        };
        appendJitEntries("jit.external_headers", "${extra_headers}");
        appendJitEntries("jit.external_libs", "${extra_libs}");
        appendJitEntries("jit.external_header_paths", "${extra_header_paths};" + requiredJitFilesPath);
        appendJitEntries("jit.external_lib_paths", "${extra_lib_paths}");
    }
