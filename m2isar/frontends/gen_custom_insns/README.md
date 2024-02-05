# Frontend to generate a m2isar Metamodel instruction set

This frontend can be used to generate a custom instruction set.

## Format

This format should be placed into a yaml file

```yaml
metadata: 
  name: # Name of the ISA extension, is used as the name in CoreDSL
  prefix: # Prefix for every instruction without '.' (e.g. cv.XXX), can be ommited
  version: # Version of the specification file, currently not used
  extensions: # Used Risc-V Extensions, could be used in  the future to expand opcode space
  extends: # Required Risc-V extensions, 
  xlen: # Defaults to 32 if unspecified
  core_name: # Only needs to be specified if a core will be generated(flag -c)
  core_template:  # Default CoreDSL file imports, Options:
                  #   None: only specified extensions
                  #   "etiss": imports etiss specific CoreDSL files



defaults:
# Section were default operators can be specified
# e.g. if rd is specified here but left out in an 
# instructions operand list the default rd will automaticly be used 
  operands:
    rd:
      width: 32
      sign: s


instruction_group:
- name: "{op}{rsX.sign}{rsX.width}" # assembly mnemonic of the instruction
  op: [op1, op2, op3] # only instructions which use the same set of operands are allowed, so sci and sc cant be mixed
  operands: # list of operands
    rs1: &anchor # &anchors can be used to avoid copy/paste of sections
      width: [8, 16, 32] # selection of bit widths
      sign: [u, s, us] # signdness can be specified per bitwidth as unsigned, signed or both
    rs2: # "*anchor" can be used to copy every key operand 
      <<: *anchor # this instead copies the keys of an anchored section, without overriding existing keys
      sign: rs1  # the key of another operand can be specified to use the same sign (or width)
    ls3:
      immediate: true
      width: 5
      sign: s
    # rd: # can be ommited as there is a default
      # width: 32
      # sign: s
```
