import logging
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional
import re
import os

# Assuming a hypothetical OCR engine if needed
# from src.ocr.ocr_engine import OCREngine

# Assuming a global config for document loader registration
from src.knowledge import register_document_loader

logger = logging.getLogger(__name__)

class PDFDocumentLoader:
    """
    Loads and processes PDF documents, extracting text, metadata, and
    conceptually handling tables and images. It aims to clean the text
    while preserving the document's structure for RAG purposes.
    """
    def __init__(self, ocr_engine: Any = None):
        self.ocr_engine = ocr_engine
        logger.info("PDFDocumentLoader initialized.")

    def load_document(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Loads a PDF document and extracts its content and metadata.

        Args:
            file_path (str): The path to the PDF file.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing 'content' (list of pages),
                                      'metadata', and 'structure' if successful, None otherwise.
        """
        if not os.path.exists(file_path):
            logger.error(f"PDF file not found: {file_path}")
            return None
        
        try:
            document = fitz.open(file_path)
            content_pages: List[str] = []
            structure_pages: List[Dict[str, Any]] = [] # To capture structural elements
            
            metadata = self._extract_metadata(document)
            metadata["file_path"] = file_path
            metadata["num_pages"] = document.page_count

            for page_num in range(document.page_count):
                page = document.load_page(page_num)
                page_text = page.get_text("text")
                
                # Apply cleaning: remove headers, footers, page numbers
                cleaned_text = self._clean_page_text(page_text, page_num + 1)
                content_pages.append(cleaned_text)

                # Conceptual: Table and Image extraction (more complex, often requires layout analysis)
                page_structure = {
                    "page_number": page_num + 1,
                    "text_content": cleaned_text,
                    "tables": self._detect_and_extract_tables(page), # Placeholder
                    "images_ocr": self._extract_and_ocr_images(page) # Placeholder
                }
                structure_pages.append(page_structure)

            document.close()
            logger.info(f"Successfully loaded and processed PDF: {file_path}")
            return {
                "content": content_pages,
                "metadata": metadata,
                "structure": structure_pages
            }

        except Exception as e:
            logger.error(f"Error loading or processing PDF '{file_path}': {e}", exc_info=True)
            return None

    def _extract_metadata(self, document: fitz.Document) -> Dict[str, Any]:
        """Extracts metadata from the PDF document."""
        meta = document.metadata
        return {
            "title": meta.get("title"),
            "author": meta.get("author"),
            "creation_date": meta.get("creationDate"),
            "mod_date": meta.get("modDate"),
            "producer": meta.get("producer"),
            "subject": meta.get("subject"),
            "keywords": meta.get("keywords")
        }

    def _clean_page_text(self, text: str, page_number: int) -> str:
        """
        Removes common headers, footers, and page numbers.
        This is a heuristic and may need fine-tuning for specific document layouts.
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        # Remove lines that look like page numbers or simple headers/footers
        for line in lines:
            line_stripped = line.strip()
            # Heuristic: if line is just the page number, or short/numeric header/footer
            if line_stripped == str(page_number): # Remove exact page number
                continue
            if re.match(r'^-?\s*\d+\s*-?$', line_stripped): # Matches - 1 -, 1, etc.
                continue
            if len(line_stripped) < 10 and re.search(r'\d', line_stripped): # Short line with numbers, often headers
                continue
            
            # More advanced: check if line repeats across all pages (header/footer)
            # This would require analyzing multiple pages together.
            
            cleaned_lines.append(line)
        
        return "\n".join(cleaned_lines).strip()

    def _detect_and_extract_tables(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """
        (Conceptual) Detects and extracts tables from a PDF page.
        This typically involves layout analysis libraries like Camelot or Tabula-py.
        """
        # Example placeholder:
        # tables = tabula.read_pdf(page.parent.name, pages=page.number, output_format="json")
        logger.debug(f"Conceptual table detection on page {page.number} (not implemented).")
        return []

    def _extract_and_ocr_images(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """
        (Conceptual) Extracts images from a PDF page and performs OCR if an OCR engine is provided.
        """
        extracted_images = []
        # for img_index, img_info in enumerate(page.get_images(full=True)):
        #     xref = img_info[0]
        #     base_image = page.parent.extract_image(xref)
        #     image_bytes = base_image["image"]
        #     
        #     ocr_text = ""
        #     if self.ocr_engine:
        #         ocr_text = self.ocr_engine.perform_ocr(image_bytes)
        #     
        #     extracted_images.append({
        #         "image_id": f"img_{{page.number}}_{img_index}",
        #         "ocr_text": ocr_text,
        #         "image_type": base_image["ext"]
        #     })
        logger.debug(f"Conceptual image OCR on page {page.number} (not implemented).")
        return []

# Register the PDF loader with the knowledge module's registry
register_document_loader("pdf", PDFDocumentLoader)


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Create a dummy PDF file for testing (requires reportlab)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        def create_dummy_pdf(filename="dummy_medical_doc.pdf"):
            c = canvas.Canvas(filename, pagesize=letter)
            c.drawString(100, 750, "Medical Textbook - Chapter 1")
            c.drawString(100, 730, "Author: Dr. AI Assistant")
            c.drawString(100, 700, "Page 1")
            c.drawString(100, 680, "This is some important medical information about cardiovascular health.")
            c.drawString(100, 660, "Lorem ipsum dolor sit amet, consectetur adipiscing elit.")
            c.showPage()
            
            c.drawString(100, 750, "Medical Textbook - Chapter 1 (cont.)")
            c.drawString(100, 730, "Page 2")
            c.drawString(100, 700, "Hypertension is a common condition where blood pressure is persistently high.")
            c.drawString(100, 680, "A table might be here:")
            # c.drawInlineImage("dummy_image.png", 100, 500, width=50, height=50) # Conceptual image
            c.save()
            logger.info(f"Dummy PDF '{filename}' created.")
            return filename
        
        dummy_pdf_file = create_dummy_pdf()
    except ImportError:
        print("ReportLab not installed. Skipping dummy PDF creation. Please provide a PDF manually for testing.")
        dummy_pdf_file = None

    if dummy_pdf_file and os.path.exists(dummy_pdf_file):
        try:
            pdf_loader = PDFDocumentLoader()
            document_data = pdf_loader.load_document(dummy_pdf_file)

            if document_data:
                print("\n--- Extracted Metadata ---")
                for key, value in document_data["metadata"].items():
                    print(f"{key}: {value}")

                print("\n--- Extracted Content (Page 1) ---")
                print(document_data["content"][0])
                assert "Page 1" not in document_data["content"][0] # Check cleaning

                print("\n--- Extracted Content (Page 2) ---")
                print(document_data["content"][1])
                assert "Page 2" not in document_data["content"][1] # Check cleaning
                assert "Hypertension is a common condition" in document_data["content"][1]

                print("\n--- Document Structure (Conceptual) ---")
                print(f"Page 1 structure (text): {document_data['structure'][0]['text_content'][:100]}...")
                print(f"Page 1 tables (conceptual): {document_data['structure'][0]['tables']}")
                print(f"Page 1 images (conceptual): {document_data['structure'][0]['images_ocr']}")

        except Exception as e:
            logger.error(f"Error during PDF loading example: {e}")
        finally:
            if os.path.exists(dummy_pdf_file):
                os.remove(dummy_pdf_file)
                logger.info(f"Cleaned up dummy PDF: {dummy_pdf_file}")
    else:
        logger.warning("No dummy PDF file available or created. Cannot run example.")
