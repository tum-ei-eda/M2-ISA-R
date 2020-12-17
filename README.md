# M2-ISA-R v2

This tool generates architecture models for ETISS from CoreDSL source files or abstract model trees.

## Installation
- Clone the repository, change into its root
- Create a Python virtualenv: ```python3 -m venv venv```
- Activate venv: ```source venv/bin/activate``` (might differ on Windows)


## Usage
M2-ISA-R v2 is divided into two separate tools: Parser and Writer.

To parse a CoreDSL description: ```./parse-coredsl.py [-j threads] path/to/input```
To generate ETISS Architecture: ```./etiss_writer_coredsl.py path/to/input```

Notes:
- ```path/to/input``` stays the same for both calls if the same model is compiled
- The intermediate and output files are put into ```path/to/input/gen_model``` and ```path/to/input/gen_output```, respectively.
