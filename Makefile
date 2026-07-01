# Makefile for common riffy development tasks.
# Targets use uv (https://docs.astral.sh/uv/) to manage the environment and
# run tools. Install uv first: https://docs.astral.sh/uv/getting-started/install/

UV ?= uv

.DEFAULT_GOAL := help

.PHONY: help install install-docs test coverage lint format format-check \
        typecheck check build docs docs-serve examples examples-python \
        examples-bash precommit clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Sync the environment with dev dependencies
	$(UV) sync --extra dev

install-docs:  ## Sync the environment with docs dependencies
	$(UV) sync --extra docs

test:  ## Run the test suite
	$(UV) run --extra dev pytest

coverage:  ## Run the test suite with a coverage report
	$(UV) run --extra dev pytest --cov=riffy --cov-report=term-missing

lint:  ## Lint with Ruff
	$(UV) run --extra dev ruff check .

format:  ## Format the code with Ruff
	$(UV) run --extra dev ruff format .

format-check:  ## Check formatting with Ruff (no changes)
	$(UV) run --extra dev ruff format --check .

typecheck:  ## Type-check with mypy
	$(UV) run --extra dev mypy

check: lint format-check typecheck test  ## Run all CI checks locally

build:  ## Build the sdist and wheel into dist/
	$(UV) build

docs:  ## Build the documentation site (strict)
	$(UV) run --extra docs mkdocs build --strict

docs-serve:  ## Serve the docs locally with live reload
	$(UV) run --extra docs mkdocs serve

examples-python:  ## Run the Python example scripts
	$(UV) run python examples/python/run_all.py -v

examples-bash:  ## Run the bash CLI examples
	$(UV) run bash examples/bash/run_all.sh -v

examples: examples-python examples-bash  ## Run all examples (python + bash)

precommit:  ## Run pre-commit on all files
	$(UV)x pre-commit run --all-files

clean:  ## Remove build, test, and cache artifacts
	rm -rf build/ dist/ *.egg-info src/*.egg-info src/riffy.egg-info site/ \
		htmlcov/ .coverage coverage.xml .pytest_cache/ .ruff_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
