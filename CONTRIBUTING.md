# Contributing to Vulcan

Thank you for your interest in contributing to Vulcan! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Submitting Issues](#submitting-issues)
- [Submitting Pull Requests](#submitting-pull-requests)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Create a new branch for your feature or bugfix.
4. Make your changes, following the coding standards below.
5. Run all tests and ensure they pass.
6. Submit a pull request.

## Development Environment Setup

### Backend (Python)

The backend requires **Python 3.14** or later.

```bash
# Create a virtual environment
python3.14 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Install dev dependencies
pip install -r backend/requirements-dev.txt

# Run the backend
python -m backend.main
```

### Frontend (Node.js)

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev

# Build for production
npm run build
```

### Running with Docker

```bash
docker compose up --build
```

## Submitting Issues

- Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) for bugs.
- Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md) for new feature ideas.
- Search existing issues before creating a new one.
- Provide as much detail as possible, including steps to reproduce for bugs.

## Submitting Pull Requests

1. Ensure your branch is up to date with `main`.
2. Fill out the [pull request template](.github/PULL_REQUEST_TEMPLATE.md) completely.
3. Link any related issues.
4. Request a review from a maintainer.
5. Address review feedback promptly.

### PR Guidelines

- Keep PRs focused — one feature or fix per PR.
- Write clear commit messages.
- Do not commit secrets, credentials, or private keys.
- Update documentation if your change affects user-facing behavior.

## Coding Standards

### Python

- **Linter/Formatter**: [Ruff](https://docs.astral.sh/ruff/) is used for linting and formatting. Run `ruff check .` and `ruff format .` before committing.
- **Type Hints**: All function signatures must include type hints. Use `mypy` or `pyright` for static type checking.
- **Docstrings**: Use Google-style docstrings for all public functions and classes.
- **Imports**: Use absolute imports. Ruff will enforce import sorting.

### TypeScript

- **Strict Mode**: TypeScript strict mode is enabled (`"strict": true` in `tsconfig.json`). All code must compile without errors.
- **Linter**: Follow the ESLint configuration provided in the project.
- **Formatting**: Use Prettier with the project's configuration.

### General

- Keep functions small and focused.
- Write self-documenting code with clear variable and function names.
- Comment non-obvious logic.

## Testing Requirements

> **All tests must pass before a PR can be merged.**

### Backend Tests

```bash
# Run all backend tests
pytest

# Run with coverage
pytest --cov=backend
```

### Frontend Tests

```bash
cd frontend
npm test
```

### Before Submitting

- [ ] All existing tests pass.
- [ ] New code includes appropriate tests.
- [ ] No secrets or credentials are committed.
- [ ] Code passes linting (`ruff check .` for Python, `npm run lint` for TypeScript).

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

If you have questions about contributing, feel free to open a discussion or reach out to the maintainers.
