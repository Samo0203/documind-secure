from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> List[str]:
    """
    Split text into overlapping chunks using a recursive character-based strategy.
    Tries to split on paragraphs, then sentences, then words, then characters.
    """
    if not text or not text.strip():
        return []

    separators = ["\n\n", "\n", ". ", " ", ""]
    return _split_recursive(text.strip(), chunk_size, overlap, separators)


def _split_recursive(text: str, chunk_size: int, overlap: int, separators: List[str]) -> List[str]:
    """Recursively split text using different separators."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    separator = separators[0] if separators else ""
    remaining_separators = separators[1:]

    parts = text.split(separator) if separator else list(text)
    chunks: List[str] = []
    current_chunk = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        candidate = (current_chunk + separator + part).strip() if current_chunk else part

        if len(candidate) <= chunk_size:
            current_chunk = candidate
        else:
            # Save current chunk if it has content
            if current_chunk:
                chunks.append(current_chunk)

            # If the part itself is too large, recurse
            if len(part) > chunk_size and remaining_separators:
                sub_chunks = _split_recursive(part, chunk_size, overlap, remaining_separators)
                # Add overlap from the last saved chunk to the first sub-chunk
                if chunks and sub_chunks:
                    overlap_text = chunks[-1][-overlap:] if len(chunks[-1]) > overlap else chunks[-1]
                    sub_chunks[0] = (overlap_text + " " + sub_chunks[0]).strip()
                chunks.extend(sub_chunks)
                current_chunk = ""
            else:
                # Add overlap from previous chunk
                if chunks:
                    overlap_text = chunks[-1][-overlap:] if len(chunks[-1]) > overlap else chunks[-1]
                    current_chunk = (overlap_text + " " + part).strip()
                else:
                    current_chunk = part

    if current_chunk:
        chunks.append(current_chunk)

    return [c for c in chunks if c.strip()]
