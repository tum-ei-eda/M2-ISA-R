# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import setuptools

setuptools.setup(
    name="m2isar",
    url="https://github.com/tum-ei-eda/m2-isa-r",
    use_scm_version=True,
    packages=setuptools.find_packages(),
    package_data={
        "": ["*.mako"]
    },
    setup_requires=["setuptools_scm"],
    install_requires=[
        "mako",
        "antlr4-python3-runtime == 4.13.1"
    ],
    entry_points={
        "console_scripts": [
            "etiss_writer=m2isar.backends.etiss.writer:main",
            "coredsl2_parser=m2isar.frontends.coredsl2.parser:main",
            "m2isar_viewer=m2isar.backends.viewer.viewer:main"
        ]
    },
    zip_safe=False
)
