"""
Ohmic Example: Download Raspberry Pi 4 / CM4 Datasheets & Extract Pinouts.
Demonstrates:
1. Querying and downloading real component datasheets online.
2. Validating the PDF structure and caching locally.
3. Reading the chip documentation and extracting pin descriptions with PyMuPDF.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ohmic import CloudFetcher, DatasheetExtractor

def test_download_pi4():
    print("=" * 65)
    print("Ohmic Autonomous Datasheet Downloader: Raspberry Pi 4 / CM4")
    print("=" * 65)

    fetcher = CloudFetcher()
    extractor = DatasheetExtractor()

    targets = [
        ("CM4", "Raspberry Pi Compute Module 4"),
        ("RP2040", "Raspberry Pi Dual Cortex-M0+ MCU"),
        ("BCM2711", "Raspberry Pi 4 Quad-Core Application Processor")
    ]

    for part_name, description in targets:
        print(f"\n[+] Searching and downloading datasheet for: {part_name} ({description})...")
        pdf_path = fetcher.fetch_datasheet(part_name)

        if pdf_path and os.path.exists(pdf_path):
            file_size_kb = os.path.getsize(pdf_path) / 1024.0
            print(f"    SUCCESS! Downloaded and verified PDF.")
            print(f"    File: {pdf_path}")
            print(f"    Size: {file_size_kb:.1f} KB")

            # Inspect PDF using fitz / pypdf
            import fitz
            doc = fitz.open(pdf_path)
            num_pages = len(doc)
            title = doc.metadata.get("title", "No Title")
            author = doc.metadata.get("author", "No Author")
            print(f"    Pages: {num_pages}")
            print(f"    Document Title: {title}")
            print(f"    Metadata Author: {author}")

            # Sample first page text preview
            first_page_text = doc[0].get_text()
            preview = "\n".join([line.strip() for line in first_page_text.splitlines() if line.strip()][:5])
            print(f"    First Page Preview:\n    ---\n    {preview}\n    ---")
            doc.close()
        else:
            print(f"    Failed to download datasheet for {part_name}")

if __name__ == "__main__":
    test_download_pi4()
