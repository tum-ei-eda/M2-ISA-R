<%page args="instr_=None, bitfields=None, builder_=None" />
    % for bf_i in bitfields:
    int ${bf_i} = 0;
    % for br_i in builder_.getAllBitRanges(instr_, bf_i):
    static etiss::instr::BitArrayRange R_${bf_i}_${br_i.offset}(${br_i.msb},${br_i.lsb});
    ${bf_i} += R_${bf_i}_${br_i.offset}.read(ba) << ${br_i.offset};
    % endfor
    % endfor
