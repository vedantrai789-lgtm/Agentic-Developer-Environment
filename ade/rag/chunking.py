import ast

import tiktoken

from ade.rag.types import Chunk, ChunkMetadata

# Cache the tokenizer at module level (thread-safe)
_encoder = tiktoken.get_encoding("cl100k_base")

MIN_CHUNK_TOKENS = 10


def _count_tokens(text: str) -> int:
    """Count tokens using tiktoken cl100k_base encoding."""
    return len(_encoder.encode(text))


def _get_source_lines(source: str, node: ast.AST) -> str:
    """Extract source text for an AST node using line numbers."""
    lines = source.splitlines(keepends=True)
    # Include decorators if present
    start = getattr(node, "lineno", 1) - 1
    if hasattr(node, "decorator_list") and node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    end = getattr(node, "end_lineno", len(lines))
    return "".join(lines[start:end])


def _extract_imports(source: str) -> str:
    """Extract all import statements from a Python source file."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""

    lines = source.splitlines(keepends=True)
    import_lines = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            import_lines.extend(lines[start:end])
    return "".join(import_lines)


def chunk_python_file(content: str, file_path: str) -> list[Chunk]:
    """Chunk a Python file using AST parsing.

    Extracts functions and classes as individual chunks.
    Falls back to text chunking on syntax errors.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return chunk_text_file(content, file_path)

    chunks: list[Chunk] = []
    imports = _extract_imports(content)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            source = _get_source_lines(content, node)
            text = f"{imports}\n{source}" if imports else source
            start_line = node.lineno
            if node.decorator_list:
                start_line = node.decorator_list[0].lineno
            token_count = _count_tokens(text)

            if token_count >= MIN_CHUNK_TOKENS:
                chunks.append(Chunk(
                    text=text,
                    metadata=ChunkMetadata(
                        file_path=file_path,
                        chunk_type="function",
                        start_line=start_line,
                        end_line=node.end_lineno or node.lineno,
                        token_count=token_count,
                    ),
                ))

        elif isinstance(node, ast.ClassDef):
            source = _get_source_lines(content, node)
            text = f"{imports}\n{source}" if imports else source
            start_line = node.lineno
            if node.decorator_list:
                start_line = node.decorator_list[0].lineno
            token_count = _count_tokens(text)

            if token_count >= MIN_CHUNK_TOKENS:
                chunks.append(Chunk(
                    text=text,
                    metadata=ChunkMetadata(
                        file_path=file_path,
                        chunk_type="class",
                        start_line=start_line,
                        end_line=node.end_lineno or node.lineno,
                        token_count=token_count,
                    ),
                ))

    # If no functions/classes found (e.g., a script or config file), chunk as text
    if not chunks:
        return chunk_text_file(content, file_path)

    # Add module-level docstring + imports as a "module" chunk if substantial
    module_docstring = ast.get_docstring(tree) or ""
    module_text = f"{imports}\n{module_docstring}".strip() if module_docstring else imports.strip()
    if module_text and _count_tokens(module_text) >= MIN_CHUNK_TOKENS:
        chunks.insert(0, Chunk(
            text=module_text,
            metadata=ChunkMetadata(
                file_path=file_path,
                chunk_type="module",
                start_line=1,
                end_line=tree.body[0].lineno if tree.body else 1,
                token_count=_count_tokens(module_text),
            ),
        ))

    return chunks


def chunk_text_file(content: str, file_path: str, max_tokens: int = 500) -> list[Chunk]:
    """Chunk a text file by splitting on double newlines.

    Merges small paragraphs and splits large ones to fit the token budget.
    """
    if not content.strip():
        return []

    # Split on double newlines (paragraph boundaries)
    paragraphs = content.split("\n\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks: list[Chunk] = []
    current_text = ""
    current_start_line = 1

    # Track line positions
    line_offset = 1

    for para in paragraphs:
        para_lines = para.count("\n") + 1
        para_tokens = _count_tokens(para)

        if para_tokens > max_tokens:
            # Flush current buffer first
            if current_text:
                token_count = _count_tokens(current_text)
                if token_count >= MIN_CHUNK_TOKENS:
                    chunks.append(Chunk(
                        text=current_text,
                        metadata=ChunkMetadata(
                            file_path=file_path,
                            chunk_type="block",
                            start_line=current_start_line,
                            end_line=line_offset - 1,
                            token_count=token_count,
                        ),
                    ))
                current_text = ""

            # Split large paragraph by lines
            lines = para.split("\n")
            sub_text = ""
            sub_start = line_offset
            for line in lines:
                candidate = f"{sub_text}\n{line}".strip() if sub_text else line
                if _count_tokens(candidate) > max_tokens and sub_text:
                    token_count = _count_tokens(sub_text)
                    if token_count >= MIN_CHUNK_TOKENS:
                        chunks.append(Chunk(
                            text=sub_text,
                            metadata=ChunkMetadata(
                                file_path=file_path,
                                chunk_type="block",
                                start_line=sub_start,
                                end_line=line_offset - 1,
                                token_count=token_count,
                            ),
                        ))
                    sub_text = line
                    sub_start = line_offset
                else:
                    sub_text = candidate
                line_offset += 1
            if sub_text:
                token_count = _count_tokens(sub_text)
                if token_count >= MIN_CHUNK_TOKENS:
                    chunks.append(Chunk(
                        text=sub_text,
                        metadata=ChunkMetadata(
                            file_path=file_path,
                            chunk_type="block",
                            start_line=sub_start,
                            end_line=line_offset - 1,
                            token_count=token_count,
                        ),
                    ))
                sub_text = ""
            current_start_line = line_offset
            line_offset += 1  # blank line between paragraphs
            continue

        # Try merging with current buffer
        candidate = f"{current_text}\n\n{para}".strip() if current_text else para
        if _count_tokens(candidate) > max_tokens and current_text:
            # Flush current buffer
            token_count = _count_tokens(current_text)
            if token_count >= MIN_CHUNK_TOKENS:
                chunks.append(Chunk(
                    text=current_text,
                    metadata=ChunkMetadata(
                        file_path=file_path,
                        chunk_type="block",
                        start_line=current_start_line,
                        end_line=line_offset - 1,
                        token_count=token_count,
                    ),
                ))
            current_text = para
            current_start_line = line_offset
        else:
            current_text = candidate
            if not current_text or current_text == para:
                current_start_line = line_offset

        line_offset += para_lines + 1  # +1 for blank line between paragraphs

    # Flush remaining
    if current_text:
        token_count = _count_tokens(current_text)
        if token_count >= MIN_CHUNK_TOKENS:
            chunks.append(Chunk(
                text=current_text,
                metadata=ChunkMetadata(
                    file_path=file_path,
                    chunk_type="block",
                    start_line=current_start_line,
                    end_line=line_offset - 1,
                    token_count=token_count,
                ),
            ))

    return chunks


def chunk_file(content: str, file_path: str) -> list[Chunk]:
    """Dispatch to the appropriate chunking strategy based on file extension."""
    if file_path.endswith(".py"):
        return chunk_python_file(content, file_path)
    return chunk_text_file(content, file_path)
