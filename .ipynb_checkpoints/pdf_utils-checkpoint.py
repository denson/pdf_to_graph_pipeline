# pdf_utils.py

import pymupdf

def extract_text_from_pdf(pdf_path: str) -> str:
    text_content = ""
    try:
        doc = pymupdf.open(pdf_path)  # Open the PDF
        for page in doc:
            text_content += page.get_text()
        doc.close()
    except Exception as e:
        print(f"[ERROR] Failed to read PDF {pdf_path}: {e}")
        return ""
    return text_content
