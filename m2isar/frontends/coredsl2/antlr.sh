#!/bin/bash

java -jar ../../../ext/antlr-4.10.1-complete.jar -o parser_gen -listener -visitor -Dlanguage=Python3 CoreDSL2.g4