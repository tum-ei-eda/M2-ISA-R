# SPDX-License-Identifier: Apache-2.0
"""Compatibility imports for the unified CoreDSL writer."""
from ..coredsl2.writer import gen_cdsl_code, write_includes, main
from ..coredsl2.utils import CoreDSL2Writer as _CoreDSL2Writer
from ..coredsl2.visitor import CDSLWriterVisitor


class CoreDSL2Writer(_CoreDSL2Writer):
    """Preserve the old constructor; all serialization lives in coredsl2."""
    def __init__(self, legacy=False):
        super().__init__(CDSLWriterVisitor(), reduced=False, legacy=legacy)


if __name__ == "__main__":
    main()
