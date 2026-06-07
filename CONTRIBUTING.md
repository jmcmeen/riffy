# Contributing to riffy

Thanks for your interest in contributing! This guide explains how to set up your
environment, make changes, and submit a pull request. Please be respectful and
constructive in all project interactions.

## Getting Started

1. Fork the repository and clone your fork:

   ```bash
   git clone https://github.com/<your-username>/riffy.git
   cd riffy
   ```

2. Create and activate a virtual environment (Python 3.10+):

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

3. Install the package with development dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

4. (Optional but recommended) install the pre-commit hooks:

   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Development Workflow

Create a feature branch off `main`:

```bash
git checkout -b feature/short-description
```

Make your change, then run the full local check suite before opening a PR:

```bash
ruff check .          # lint
ruff format .         # format (use --check in CI)
mypy                  # type-check
pytest                # run the test suite
pytest --cov=riffy --cov-report=term-missing   # with coverage
```

All of these run automatically in CI on every pull request, so running them
locally first keeps the feedback loop fast.

### Makefile shortcuts

A `Makefile` wraps the common tasks. Run `make help` to list every target:

```bash
make install   # pip install -e ".[dev]"
make check     # lint + format-check + typecheck + test (the CI gate)
make test      # run the test suite
make coverage  # tests with a coverage report
make format    # auto-format with Ruff
make docs      # build the docs (use make docs-serve to preview)
```

The targets call tools via `python -m ...`, so activate your virtualenv first
(or pass `make PYTHON=.venv/bin/python <target>`).

## Guidelines

- **Tests:** Add or update tests for any behavior change. The suite aims to stay
  at/near 100% coverage. Tests live in `tests/` and generate their own WAV files
  via fixtures in `tests/conftest.py` (no binary fixtures are committed).
- **Types:** The library is fully typed and ships a `py.typed` marker. Keep new
  code typed and `mypy`-clean.
- **Style:** Code is formatted and linted with Ruff (line length 100). Run
  `ruff format .` and `ruff check --fix .` before committing.
- **Docs:** Update `README.md`, docstrings, and the docs in `docs/` when you
  change the public API. Docstrings drive the generated API reference.
- **Changelog:** Add a note under an "Unreleased"/next-version heading in
  [CHANGELOG.md](CHANGELOG.md) describing your change.
- **Commits:** Write clear, descriptive commit messages.

## Building the Documentation

```bash
pip install -e ".[docs]"
mkdocs serve   # preview at http://127.0.0.1:8000
mkdocs build --strict
```

## Submitting a Pull Request

1. Push your branch to your fork.
2. Open a pull request against `main` and fill out the PR template.
3. Ensure CI is green and address any review feedback.

## Reporting Bugs and Requesting Features

Please use the [issue templates](https://github.com/jmcmeen/riffy/issues/new/choose).
For security issues, see [SECURITY.md](SECURITY.md) instead of opening a public issue.

## License

By contributing, you agree that your contributions will be licensed under the
project's [MIT License](LICENSE).
