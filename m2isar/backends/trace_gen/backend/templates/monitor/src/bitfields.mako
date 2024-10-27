<%page args="instr_=None" />
    % for bf_i in instr_.getAllBitfields():
    int ${bf_i.name} = 0;
    % for br_i in bf_i.getAllBitRanges():
    static etiss::instr::BitArrayRange R_${bf_i.name}_${br_i.offset}(${br_i.msb},${br_i.lsb});
    ${bf_i.name} += R_${bf_i.name}_${br_i.offset}.read(ba) << ${br_i.offset};
    % endfor
    % endfor
