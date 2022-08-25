# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
sys.path.insert(0, os.path.abspath('../..'))

project = 'M2-ISA-R'
copyright = '2022, TUM EDA'
author = 'TUM EDA'
release = '0.0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    #'sphinx.ext.autodoc',
    #'sphinx.ext.autosummary',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    #'sphinx_autodoc_typehints',
    'autoapi.extension'
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'mako': ('https://docs.makotemplates.org/en/latest/', None),
    'lark-parser': ('https://lark-parser.readthedocs.io/en/latest/', None)
}

autoapi_type = 'python'
autoapi_dirs = ['../../m2isar']
autoapi_options = [
    'members',
    #'inherited-members',
    'undoc-members',
    'private-members',
    'show-inheritance',
    'show-inheritance-diagram',
    'show-module-summary',
    'special-members',
    'imported-members'
]
autoapi_ignore = [
    '*migrations*',
    #'*parser_gen*'
]

templates_path = ['_templates']
exclude_patterns = []

#html_show_sourcelink = True  # Remove 'view source code' from top of page (for html, not python)
#autodoc_typehints = "description" # Sphinx-native method. Not as good as sphinx_autodoc_typehints
add_module_names = False # Remove namespaces from class/method signatures


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# -- Options for todo extension ----------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/todo.html#configuration

todo_include_todos = True
