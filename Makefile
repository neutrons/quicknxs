# bash sell to correctly interpret the double brackets in the conditions below
SHELL=/bin/bash
# https://www.gnu.org/software/make/manual/html_node/One-Shell.html
# Required to prevent having to use "conda init"

# all the lines in a recipe are passed to a single invocation of the shell.
.ONESHELL:

PREFIX := /SNS/REF_M/shared

help:
    # this nifty perl one-liner collects all commnents headed by the double "#" symbols next to each target and recycles them as comments
	@perl -nle'print $& if m{^[a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

# list of all phony targets, alphabetically sorted
.PHONY: docs

docs:  ## create HTML docs under docs/_build/html/. Requires activation of the drtsans conda environment
	# this will fail on a warning
	@cd docs&& make html SPHINXOPTS="-n" && echo -e "##########\n DOCS point your browser to file://$$(pwd)/_build/html/index.html\n##########"

docstest:  ## test doctest-style code snippets in the documentation
	# this will fail on a warning
	@cd docs&& make doctest
