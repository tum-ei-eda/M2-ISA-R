<%page args="map_=None, builder_=None" />
    % if ((map_.getTraceValue().dataType == "int") or (map_.getTraceValue().dataType == "uint64_t")):
    ret_strs << "${builder_.getBufferName(map_.getTraceValue().name)}[*${builder_.getInstrCntName()}] = " << ${builder_.getDescriptionString(map_.getDescription())} << ";\n";
    % elif map_.getTraceValue().dataType == "string":
    ret_strs << "strcpy(${builder_.getBufferName(map_.getTraceValue().name)}[*${builder_.getInstrCntName()}],\"" << ${builder_.getDescriptionString(map_.getDescription())} << "\");\n";
    % endif