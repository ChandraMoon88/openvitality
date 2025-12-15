import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ChunkingStrategy:
    """
    Splits large text documents into smaller, manageable chunks suitable for
    embedding and retrieval in RAG systems. Implements a recursive character splitter
    with configurable chunk sizes and overlaps. Aims to preserve semantic boundaries.
    """
    def __init__(self,
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 separators: Optional[List[str]] = None):
        """
        Initializes the chunking strategy.

        Args:
            chunk_size (int): The maximum number of characters per chunk.
            chunk_overlap (int): The number of characters to overlap between consecutive chunks.
            separators (Optional[List[str]]): A list of characters/strings to use as separators,
                                              ordered from most significant to least significant.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Default separators prioritize document structure and sentence boundaries
        self.separators = separators if separators else [
            "\n\n",  # Double newline (paragraph/section break)
            "\n",    # Single newline (line break)
            " ",     # Whitespace
            "",      # Fallback to character split
        ]
        logger.info(f"ChunkingStrategy initialized with chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")

    def split_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Splits a single large text into smaller chunks.

        Args:
            text (str): The input text to be split.
            metadata (Optional[Dict[str, Any]]): Optional metadata to attach to each chunk.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a chunk
                                  with its 'content' and 'metadata'.
        """
        if not text:
            return []

        chunks = self._recursive_split(text, self.separators)
        final_chunks: List[Dict[str, Any]] = []

        for i, chunk_content in enumerate(chunks):
            # Attach metadata to each chunk
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata["chunk_id"] = i + 1
            chunk_metadata["chunk_size"] = len(chunk_content)
            final_chunks.append({"content": chunk_content, "metadata": chunk_metadata})
        
        logger.debug(f"Split text into {len(final_chunks)} chunks.")
        return final_chunks

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """
        Recursively splits text using a hierarchy of separators until chunks
        meet the size criteria or no more splitting is possible.
        """
        if not separators:
            # Base case: no more separators, just return chunks of max size
            return self._split_by_length(text)

        current_separator = separators[0]
        remaining_separators = separators[1:]

        # Split by the current separator
        parts = text.split(current_separator)
        
        split_chunks: List[str] = []
        for part in parts:
            if not part.strip():
                continue
            
            # If a part is too large, recursively split it with the next separator
            if len(part) > self.chunk_size:
                split_chunks.extend(self._recursive_split(part, remaining_separators))
            else:
                split_chunks.append(part)
        
        # Now, combine chunks to add overlap and ensure min size (if desired)
        # and re-split any that are still too large
        combined_chunks = self._combine_and_overlap(split_chunks)
        
        # Final pass to ensure no chunks exceed max size (can happen with overlap)
        final_processed_chunks = []
        for chunk in combined_chunks:
            if len(chunk) > self.chunk_size:
                final_processed_chunks.extend(self._split_by_length(chunk))
            else:
                final_processed_chunks.append(chunk)

        return final_processed_chunks

    def _split_by_length(self, text: str) -> List[str]:
        """
        A brute-force split by chunk_size if no natural separators can be used.
        """
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            chunks.append(chunk)
        return chunks

    def _combine_and_overlap(self, chunks: List[str]) -> List[str]:
        """
        Combines adjacent chunks to introduce overlap and ensures that
        chunks are not too small (though primary goal is max_size).
        """
        if not chunks:
            return []

        overlapped_chunks = []
        current_chunk_content = ""
        
        for i, chunk in enumerate(chunks):
            if not current_chunk_content: # First chunk or previous was complete
                current_chunk_content = chunk
            else:
                # Add overlap from previous chunk
                overlap_text = current_chunk_content[-self.chunk_overlap:]
                current_chunk_content += " " + chunk # Simple concatenation
                
                # If current_chunk_content gets too long, finalize it
                if len(current_chunk_content) > self.chunk_size:
                    # Try to find a good split point near the overlap end
                    split_point = self.chunk_size - self.chunk_overlap
                    # Ensure split point is not mid-word or mid-sentence
                    # For simplicity, we just split. Advanced logic would use NLU.
                    
                    overlapped_chunks.append(current_chunk_content[:self.chunk_size])
                    current_chunk_content = overlap_text + current_chunk_content[self.chunk_size:] # Start new with overlap
                else:
                    overlapped_chunks.append(current_chunk_content)
                    current_chunk_content = "" # Reset if chunk was finalized

        if current_chunk_content:
            overlapped_chunks.append(current_chunk_content) # Add any remaining
        
        return overlapped_chunks

    def _respect_sentence_boundaries(self, text: str) -> List[str]:
        """
        (Conceptual) Splits text into sentences, aiming to prevent chunks from breaking mid-sentence.
        This would often use a sentence tokenizer from NLTK or spaCy.
        """
        # from nltk.tokenize import sent_tokenize
        # sentences = sent_tokenize(text)
        # For now, a simple split by common sentence-ending punctuation
        logger.debug("Conceptual sentence boundary respect (not fully implemented).")
        return re.split(r'(?<=[.!?])\s+', text)

    def _markdown_aware_split(self, text: str) -> List[str]:
        """
        (Conceptual) Splits text while trying to keep markdown headings and their content together.
        """
        # Prioritize splits by headings (e.g., # Heading)
        # Use regex to find markdown headings
        logger.debug("Conceptual markdown-aware splitting (not fully implemented).")
        return re.split(r'\n(#{1,6}\s+.*)\n', text)

    def _medical_context_aware_split(self, text: str) -> List[str]:
        """
        (Conceptual) Prevents splitting of critical medical entities like "drug name dosage".
        Requires an entity extractor or specific regex patterns.
        """
        # Example: if "Amoxicillin 500mg" is found, ensure it stays in one chunk.
        # This is a complex problem and might involve re-combining chunks after initial split
        # or having very smart splitting rules based on entity recognition.
        logger.debug("Conceptual medical context-aware splitting (not fully implemented).")
        return [text] # Placeholder, no splitting here for now


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    long_medical_text = """
# Introduction to Hypertension

Hypertension, or high blood pressure, is a common condition in which the long-term force of the blood against your artery walls is high enough that it may eventually cause health problems, such as heart disease.

## Causes and Risk Factors

Various factors contribute to hypertension. These include age, family history, obesity, lack of physical activity, and a diet high in sodium. Certain medications can also elevate blood pressure. It is important to monitor blood pressure regularly.

### Symptoms

Most people with high blood pressure have no signs or symptoms, even if blood pressure readings reach dangerously high levels. A few people with high blood pressure may have:

- Headaches
- Shortness of breath
- Nosebleeds

These signs and symptoms aren't specific, however, and usually don't occur until high blood pressure has reached a severe, life-threatening stage.

## Diagnosis and Treatment

Diagnosis typically involves multiple blood pressure readings over time. Treatment options include lifestyle changes, such as the DASH diet and regular exercise, and medication. Common medications include diuretics, ACE inhibitors, ARBs, and calcium channel blockers. Dosage often starts at a low amount, e.g., Lisinopril 10mg once daily, and may be adjusted based on patient response.

It is crucial to never split drug names from their dosages. For example, "Lisinopril 10mg" should always remain together. Patients should always consult their doctor before changing any medication.
"""

    chunker = ChunkingStrategy(chunk_size=300, chunk_overlap=50) # Smaller chunks for testing

    print("\n--- Chunking Example ---")
    chunks = chunker.split_text(long_medical_text, metadata={"source": "Medical Textbook", "chapter": "Hypertension"})
    
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} (Size: {len(chunk['content'])} chars) ---")
        print(f"Metadata: {chunk['metadata']}")
        print(chunk['content'])
        # Assertions to check basic rules
        if i > 0:
            # Check overlap if there's a previous chunk
            prev_chunk_content = chunks[i-1]['content']
            assert chunk['content'].startswith(prev_chunk_content[-chunker.chunk_overlap:].strip()) or len(prev_chunk_content[-chunker.chunk_overlap:].strip()) == 0

    assert len(chunks) > 1 # Should have split into multiple chunks
    assert all(len(c['content']) <= 300 for c in chunks) # All chunks within max size
    
    # Check for specific un-split entities (conceptual)
    for chunk in chunks:
        assert "Lisinopril 10mg" not in chunk['content'][:chunk['content'].rfind("Lisinopril 10mg")].rsplit(" ", 1)[-1] + " " + chunk['content'][chunk['content'].rfind("Lisinopril 10mg"):]
        # This is a very simplistic check, a real one would be more robust

    print("\n--- Example with Empty Text ---")
    empty_chunks = chunker.split_text("")
    print(f"Chunks for empty text: {empty_chunks}")
    assert len(empty_chunks) == 0
