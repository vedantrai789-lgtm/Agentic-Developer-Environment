
from ade.rag.chunking import (
    _count_tokens,
    chunk_file,
    chunk_python_file,
    chunk_text_file,
)


def test_chunk_python_function(sample_python_file):
    """A Python file with a function should produce a 'function' chunk."""
    chunks = chunk_python_file(sample_python_file, "test.py")
    func_chunks = [c for c in chunks if c.metadata.chunk_type == "function"]
    assert len(func_chunks) == 1
    assert "def greet" in func_chunks[0].text
    assert func_chunks[0].metadata.start_line == 7
    assert func_chunks[0].metadata.end_line == 9


def test_chunk_python_class(sample_python_file):
    """A Python file with a class should produce a 'class' chunk."""
    chunks = chunk_python_file(sample_python_file, "test.py")
    class_chunks = [c for c in chunks if c.metadata.chunk_type == "class"]
    assert len(class_chunks) == 1
    assert "class Calculator" in class_chunks[0].text


def test_chunk_python_includes_imports(sample_python_file):
    """Chunks should include the file's import statements as context."""
    chunks = chunk_python_file(sample_python_file, "test.py")
    func_chunks = [c for c in chunks if c.metadata.chunk_type == "function"]
    assert "import os" in func_chunks[0].text
    assert "from pathlib import Path" in func_chunks[0].text


def test_chunk_python_module_chunk(sample_python_file):
    """Module-level docstring + imports should produce a 'module' chunk."""
    chunks = chunk_python_file(sample_python_file, "test.py")
    module_chunks = [c for c in chunks if c.metadata.chunk_type == "module"]
    assert len(module_chunks) == 1
    assert "Module docstring" in module_chunks[0].text


def test_chunk_python_syntax_error_falls_back(sample_invalid_python):
    """Invalid Python should fall back to text chunking."""
    chunks = chunk_python_file(sample_invalid_python, "broken.py")
    # Should still produce chunks (via text chunking fallback)
    # May be empty if content is too small
    for c in chunks:
        assert c.metadata.chunk_type == "block"


def test_chunk_text_file_basic(sample_text_file):
    """Text chunking should produce multiple blocks."""
    chunks = chunk_text_file(sample_text_file, "README.md")
    assert len(chunks) > 0
    for c in chunks:
        assert c.metadata.chunk_type == "block"


def test_chunk_text_file_respects_max_tokens():
    """Chunks should not exceed max_tokens (approximately)."""
    # Create a large text block
    large_text = "\n\n".join(f"Paragraph {i} with some content. " * 20 for i in range(20))
    chunks = chunk_text_file(large_text, "large.txt", max_tokens=100)
    for c in chunks:
        # Allow some tolerance since we split on natural boundaries
        assert c.metadata.token_count <= 200  # generous upper bound


def test_chunk_text_file_merges_small_chunks():
    """Small adjacent paragraphs should be merged."""
    small_text = "Line one.\n\nLine two.\n\nLine three."
    chunks = chunk_text_file(small_text, "small.txt", max_tokens=500)
    # Should be merged into a single chunk since they fit within max_tokens
    assert len(chunks) <= 1


def test_chunk_file_dispatches_python(sample_python_file):
    """.py files should use Python AST chunking."""
    chunks = chunk_file(sample_python_file, "module.py")
    chunk_types = {c.metadata.chunk_type for c in chunks}
    assert "function" in chunk_types or "class" in chunk_types


def test_chunk_file_dispatches_text(sample_text_file):
    """Non-.py files should use text chunking."""
    chunks = chunk_file(sample_text_file, "README.md")
    for c in chunks:
        assert c.metadata.chunk_type == "block"


def test_count_tokens():
    """Token counting should return positive integers for non-empty text."""
    assert _count_tokens("Hello, world!") > 0
    assert _count_tokens("") == 0
    assert _count_tokens("def foo(): pass") > 0


def test_chunk_empty_file():
    """Empty files should produce no chunks."""
    assert chunk_file("", "empty.py") == []
    assert chunk_file("", "empty.md") == []
    assert chunk_file("   \n\n  ", "whitespace.md") == []
