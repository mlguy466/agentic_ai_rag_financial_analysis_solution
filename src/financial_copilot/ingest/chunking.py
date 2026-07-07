"""Parent-child document chunking for SEC filings.

This module implements a hierarchical chunking strategy optimized for 10-K financial documents.
It parses SEC filing structure to identify parent sections (Items) and creates child chunks
within each section, maintaining relationships for enhanced RAG retrieval.

Key features:
- Identifies 10-K Item structure (Item 1, Item 1A, Item 7, Item 8, etc.)
- Creates parent chunks for full sections and child chunks for subsections
- Maintains metadata: ticker, filing date, section, parent_id, chunk sequence
- Optimized for Azure Search indexing and embedding

Usage:
    from financial_copilot.ingest.chunking import parse_filing, chunk_section
    
    text = read_filing_from_blob(...)
    sections = parse_filing(text)
    parent_chunks, child_chunks = chunk_section(sections[0])
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Chunk:
    """Represents a document chunk with metadata for RAG retrieval."""
    
    chunk_id: str
    """Unique identifier: parent-{parent_id} or child-{parent_id}-{sequence}"""
    
    ticker: str
    """Company ticker symbol"""
    
    text: str
    """Chunk content (up to ~1500 tokens)"""
    
    is_parent: bool
    """True if this is a parent chunk (full section), False if child"""
    
    section: str
    """SEC Item number/title (e.g., 'Item 7. Management Discussion and Analysis')"""
    
    parent_id: Optional[str] = None
    """For child chunks, reference to parent chunk_id"""
    
    sequence: int = 0
    """Chunk sequence number within parent"""
    
    metadata: dict = None
    """Additional metadata: filing_date, accession_number, etc."""
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def parse_filing_sections(text: str) -> list[dict]:
    """Parse SEC 10-K text into structured sections.
    
    Identifies Item headers (Item 1, Item 1A, Item 7, etc.) and extracts content
    for each section. Returns list of section dicts with metadata.
    
    Args:
        text: Full 10-K document text
        
    Returns:
        List of {'item': 'Item 7', 'title': '...', 'start': int, 'end': int, 'content': str}
    """
    sections = []
    
    # Pattern matches "Item N" or "Item N.A" with optional title
    # e.g., "Item 1. Business" or "Item 1A. Risk Factors"
    item_pattern = r'^(Item\s+\d+(?:[A-Z])?[\.]?)\s*(.*)$'
    
    lines = text.split('\n')
    current_section = None
    current_content: list[str] = []
    
    for i, line in enumerate(lines):
        match = re.match(item_pattern, line.strip(), re.IGNORECASE)
        
        if match:
            # Save previous section
            if current_section:
                current_section['content'] = '\n'.join(current_content).strip()
                current_section['end'] = i
                sections.append(current_section)
            
            # Start new section
            item_label = match.group(1).strip()
            title = match.group(2).strip()
            current_section = {
                'item': item_label,
                'title': title,
                'start': i,
                'content': '',
            }
            current_content = []
        elif current_section:
            current_content.append(line)
    
    # Save last section
    if current_section:
        current_section['content'] = '\n'.join(current_content).strip()
        current_section['end'] = len(lines)
        sections.append(current_section)
    
    return sections


def chunk_section_text(
    section_text: str,
    max_chunk_size: int = 1500,
    overlap: int = 150,
) -> list[str]:
    """Split section text into child chunks with overlap.
    
    Uses token-aware splitting (approximated by character count) to create
    chunks of roughly max_chunk_size tokens with overlap for context preservation.
    
    Args:
        section_text: Content of a single section
        max_chunk_size: Target chunk size in tokens (rough approximation: ~4 chars per token)
        overlap: Number of tokens to overlap between chunks
        
    Returns:
        List of chunk texts
    """
    # Rough conversion: 1 token ≈ 4 characters
    max_chars = max_chunk_size * 4
    overlap_chars = overlap * 4
    
    if len(section_text) <= max_chars:
        return [section_text]
    
    chunks = []
    start = 0
    
    while start < len(section_text):
        # Find end position
        end = start + max_chars
        
        if end >= len(section_text):
            # Last chunk
            chunks.append(section_text[start:])
            break
        
        # Try to break at sentence boundary
        last_period = section_text.rfind('.', start, end)
        if last_period > start + max_chars * 0.5:  # Reasonable sentence found
            end = last_period + 1
        else:
            # Break at paragraph or word boundary
            last_newline = section_text.rfind('\n', start, end)
            if last_newline > start:
                end = last_newline
            else:
                # Break at last space
                last_space = section_text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
        
        chunks.append(section_text[start:end].strip())
        
        # Move start position with overlap
        start = end - overlap_chars
    
    return [c for c in chunks if c]  # Filter empty chunks


def create_parent_child_chunks(
    ticker: str,
    sections: list[dict],
    metadata: dict | None = None,
) -> tuple[list[Chunk], list[Chunk]]:
    """Create parent and child chunks from parsed sections.
    
    For each section:
    - Creates a parent chunk containing the full section
    - Creates child chunks by splitting the section content
    - Links child chunks to parent via parent_id
    
    Args:
        ticker: Company ticker symbol
        sections: Parsed sections from parse_filing_sections()
        metadata: Additional metadata (filing_date, accession_number, etc.)
        
    Returns:
        (parent_chunks, child_chunks) tuple
    """
    if metadata is None:
        metadata = {}
    
    parent_chunks = []
    child_chunks = []
    
    for section_idx, section in enumerate(sections):
        item_label = section.get('item', f'Section {section_idx}')
        title = section.get('title', '')
        section_title = f"{item_label}. {title}" if title else item_label
        section_content = section.get('content', '').strip()
        
        if not section_content:
            continue
        
        # Create parent chunk
        parent_id = f"parent-{ticker}-{section_idx}"
        parent_chunk = Chunk(
            chunk_id=parent_id,
            ticker=ticker,
            text=section_content,
            is_parent=True,
            section=section_title,
            sequence=0,
            metadata={
                **metadata,
                'section_idx': section_idx,
                'section_label': item_label,
            },
        )
        parent_chunks.append(parent_chunk)
        
        # Create child chunks by splitting section content
        child_texts = chunk_section_text(section_content)
        
        for child_seq, child_text in enumerate(child_texts):
            child_id = f"child-{ticker}-{section_idx}-{child_seq}"
            child_chunk = Chunk(
                chunk_id=child_id,
                ticker=ticker,
                text=child_text,
                is_parent=False,
                section=section_title,
                parent_id=parent_id,
                sequence=child_seq,
                metadata={
                    **metadata,
                    'section_idx': section_idx,
                    'section_label': item_label,
                    'child_sequence': child_seq,
                    'total_children': len(child_texts),
                },
            )
            child_chunks.append(child_chunk)
    
    return parent_chunks, child_chunks


def chunk_filing(
    ticker: str,
    filing_text: str,
    metadata: dict | None = None,
) -> tuple[list[Chunk], list[Chunk]]:
    """End-to-end chunking: parse 10-K and create parent-child chunks.
    
    Orchestrates the full chunking pipeline:
    1. Parse filing into sections
    2. Create parent chunks (full sections)
    3. Create child chunks (subsections with overlap)
    
    Args:
        ticker: Company ticker symbol
        filing_text: Full 10-K document text
        metadata: Additional metadata (filing_date, accession_number, etc.)
        
    Returns:
        (parent_chunks, child_chunks) tuple
    """
    sections = parse_filing_sections(filing_text)
    return create_parent_child_chunks(ticker, sections, metadata)


def chunks_to_json(chunks: list[Chunk]) -> list[dict]:
    """Convert chunks to JSON-serializable dicts for storage/indexing.
    
    Args:
        chunks: List of Chunk objects
        
    Returns:
        List of dicts ready for JSON serialization and Azure Search indexing
    """
    return [
        {
            'chunk_id': c.chunk_id,
            'ticker': c.ticker,
            'text': c.text,
            'is_parent': c.is_parent,
            'section': c.section,
            'parent_id': c.parent_id,
            'sequence': c.sequence,
            'metadata': c.metadata,
        }
        for c in chunks
    ]
