# SPDX-License-Identifier: Apache-2.0
"""View instruction sets with the upstream typed model viewer."""
from .viewer import main as _main


def main(argv=None):
    return _main(argv, sets_only=True)


if __name__ == "__main__":
    main()
