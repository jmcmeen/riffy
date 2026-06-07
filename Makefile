# Makefile for common riffy development tasks.
# Override the interpreter with: make PYTHON=.venv/bin/python <target>
# (or activate your virtualenv first).

PYTHON ?= python

.DEFAULT_GOAL := help

.PHONY: help install install-docs test coverage lint format format-check \
        typecheck check build docs docs-serve precommit clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package with dev dependencies (editable)
	$(PYTHON) -m pip install -e ".[dev]"

install-docs:  ## Install the package with docs dependencies (editable)
	$(PYTHON) -m pip install -e ".[docs]"

test:  ## Run the test suite
	$(PYTHON) -m pytest

coverage:  ## Run the test suite with a coverage report
	$(PYTHON) -m pytest --cov=riffy --cov-report=term-missing

lint:  ## Lint with Ruff
	$(PYTHON) -m ruff check .

format:  ## Format the code with Ruff
	$(PYTHON) -m ruff format .

format-check:  ## Check formatting with Ruff (no changes)
	$(PYTHON) -m ruff format --check .

typecheck:  ## Type-check with mypy
	$(PYTHON) -m mypy

check: lint format-check typecheck test  ## Run all CI checks locally

build:  ## Build the sdist and wheel into dist/
	$(PYTHON) -m build

docs:  ## Build the documentation site (strict)
	$(PYTHON) -m mkdocs build --strict

docs-serve:  ## Serve the docs locally with live reload
	$(PYTHON) -m mkdocs serve

precommit:  ## Run pre-commit on all files
	$(PYTHON) -m pre_commit run --all-files

clean:  ## Remove build, test, and cache artifacts
	rm -rf build/ dist/ *.egg-info src/*.egg-info src/riffy.egg-info site/ \
		htmlcov/ .coverage coverage.xml .pytest_cache/ .ruff_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
