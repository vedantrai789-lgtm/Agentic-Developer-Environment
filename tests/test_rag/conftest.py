import pytest


@pytest.fixture
def sample_python_file():
    """A sample Python file with imports, a function, and a class."""
    return '''"""Module docstring for testing."""

import os
from pathlib import Path


def greet(name: str) -> str:
    """Return a greeting string."""
    return f"Hello, {name}!"


class Calculator:
    """A simple calculator class."""

    def __init__(self):
        self.history = []

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        result = a + b
        self.history.append(result)
        return result

    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        result = a - b
        self.history.append(result)
        return result
'''


@pytest.fixture
def sample_text_file():
    """A sample markdown file for text chunking."""
    return """# Project README

This is a sample project for testing the RAG pipeline.

## Installation

Run the following commands to install:

```
pip install -e .
docker compose up -d
```

## Usage

Import the module and call the main function.
The system will automatically process your request.

## Architecture

The system uses a multi-agent architecture with the following components:

1. Planner Agent - breaks down tasks into steps
2. Codegen Agent - generates code for each step
3. Executor Agent - runs the code in a sandbox
4. Reviewer Agent - checks the results and iterates

## Contributing

Please read CONTRIBUTING.md before submitting pull requests.
"""


@pytest.fixture
def sample_invalid_python():
    """Python file with syntax errors."""
    return """def broken_function(
    this is not valid python
    """
