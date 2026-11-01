"""
Ohmic Example: Dynamic Online Datasheet Discovery.
Demonstrates:
Searching for ANY component online, finding candidate PDF links dynamically,
downloading, and inspecting with PyMuPDF.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ohmic import CloudFetcher
import fitz

def test_dynamic_search():
    print("=" * 65)
    print("Ohmic Dynamic Online Datasheet Discovery & Download")
    print("=" * 65)

    fetcher = CloudFetcher()

    # Search for parts that have NO hardcoded URL patterns
    test_parts = ["INA219", "CH340G", "MPU6050"]

    for part in test_parts:
        print(f"\n[+] Searching the web dynamically for: {part}...")
        # Step 1: See candidate links found
        candidates = fetcher.search_online_datasheet_urls(part, limit=3)
        for i, c in enumerate(candidates, 1):
            print(f"    Candidate {i}: {c}")

        # Step 2: Download and verify
        print(f"    Downloading and verifying PDF...")
        pdf_path = fetcher.fetch_datasheet(part)

        if pdf_path and os.path.exists(pdf_path):
            size_kb = os.path.getsize(pdf_path) / 1024.0
            doc = fitz.open(pdf_path)
            title = doc.metadata.get("title", "Unknown")
            pages = len(doc)
            print(f"    SUCCESS! Cached at: {pdf_path}")
            print(f"    Size: {size_kb:.1f} KB | Pages: {pages} | Document Title: {title}")
            doc.close()
        else:
            print(f"    Failed to retrieve valid PDF for {part}")

if __name__ == "__main__":
    test_dynamic_search()
