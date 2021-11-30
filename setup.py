import setuptools

setuptools.setup(
    name="m2isar",
    url="https://github.com/tum-ei-eda/m2-isa-r",
    use_scm_version=True,
    packages=setuptools.find_packages(),
    package_data={
        "": ["*.mako", "*.lark"]
    },
    setup_requires=["setuptools_scm"],
    install_requires=[
        "mako",
        "lark-parser >= 0.11.0",
        "antlr4-python3-runtime"
    ],
    entry_points={
        "console_scripts": [
            "etiss_writer=m2isar.backends.etiss.writer:main",
            "coredsl_parser=m2isar.frontends.coredsl.parser:main",
            "coredsl2_parser=m2isar.frontends.coredsl2.parser:main"
        ]
    },
    zip_safe=False
)
