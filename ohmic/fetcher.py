"""
Ohmic Cloud Fetcher.
Pulls official KiCad symbols from GitLab/GitHub repositories on demand,
and downloads chip datasheet PDFs for automated pin extraction.
"""

import os
import re
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any, List

GITLAB_API_BASE = "https://gitlab.com/api/v4/projects/kicad%2Flibraries%2Fkicad-symbols/repository/files"

# Standard manufacturer direct datasheet patterns
MANUFACTURER_URL_PATTERNS = [
    (r"^(CM4|COMPUTE[-_ ]?MODULE[-_ ]?4)\b", "https://datasheets.raspberrypi.com/cm4/cm4-datasheet.pdf"),
    (r"^(BCM2711|PI4|RPI4|RASPBERRY[-_ ]?PI[-_ ]?4)\b", "https://datasheets.raspberrypi.com/bcm2711/bcm2711-peripherals.pdf"),
    (r"^(RP2040)\b", "https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf"),
    (r"^(RP2350)\b", "https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf"),
    (r"^(TI|MSP|LM|TL|SN|NE|TPS|INA|OPA|ADS|BQ)\w*", "https://www.ti.com/lit/ds/symlink/{part}.pdf"),
    (r"^(ESP32|ESP8266)\w*", "https://www.espressif.com/sites/default/files/documentation/{part_lower}_datasheet_en.pdf"),
    (r"^(STM32|STM8)\w*", "https://www.st.com/resource/en/datasheet/{part_lower}.pdf"),
    (r"^(MAX31865|MAX31855|MAX30102)\w*", "https://www.analog.com/media/en/technical-documentation/data-sheets/{part}.pdf"),
    (r"^(ATM90E32AS)\b", "http://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-46003-SE-M90E32AS-Datasheet.pdf"),
]

class CloudFetcher:
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".ohmic", "cloud_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.datasheet_dir = os.path.join(self.cache_dir, "datasheets")
        os.makedirs(self.datasheet_dir, exist_ok=True)
        self.symbol_dir = os.path.join(self.cache_dir, "symbols")
        os.makedirs(self.symbol_dir, exist_ok=True)

    def fetch_symbol_raw(self, lib_name: str, sym_name: str) -> Optional[str]:
        """
        Fetches a symbol (.kicad_sym) definition directly from KiCad's official GitLab repository.
        Supports both modern .kicad_symdir multi-file libraries and monolithic libraries.
        """
        # Try 1: Modern KiCad directory layout (Library.kicad_symdir/Symbol.kicad_sym)
        rel_path = f"{lib_name}.kicad_symdir/{sym_name}.kicad_sym"
        encoded_path = urllib.parse.quote_plus(rel_path)
        url = f"{GITLAB_API_BASE}/{encoded_path}/raw?ref=master"

        content = self._download_text(url)
        if content:
            return content

        # Try 2: Monolithic KiCad library layout (Library.kicad_sym)
        rel_path_mono = f"{lib_name}.kicad_sym"
        encoded_path_mono = urllib.parse.quote_plus(rel_path_mono)
        url_mono = f"{GITLAB_API_BASE}/{encoded_path_mono}/raw?ref=master"

        mono_content = self._download_text(url_mono)
        if mono_content:
            # Extract just this symbol from the monolithic library
            return self._extract_symbol_from_library(mono_content, sym_name)

        return None

    def fetch_and_cache_symbol(self, lib_id: str) -> Optional[str]:
        """
        Fetches an external symbol by 'LibName:SymName', caches it locally,
        and returns the local file path.
        """
        if ":" not in lib_id:
            return None
        lib_name, sym_name = lib_id.split(":", 1)
        
        local_path = os.path.join(self.symbol_dir, f"{lib_name}_{sym_name}.kicad_sym")
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                return f.read()

        raw_sym = self.fetch_symbol_raw(lib_name, sym_name)
        if raw_sym:
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(raw_sym)
            return raw_sym

        return None

    def download_datasheet_url(self, url: str, part_name: str) -> Optional[str]:
        """Downloads a datasheet PDF from a direct URL into the local cache."""
        dest_path = os.path.join(self.datasheet_dir, f"{part_name}.pdf")
        if os.path.exists(dest_path):
            return dest_path

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                # Verify that downloaded data is actually a PDF
                if data[:4] == b"%PDF":
                    with open(dest_path, "wb") as f:
                        f.write(data)
                    return dest_path
        except Exception:
            pass
        return None

    def get_candidate_datasheet_url(self, part_name: str) -> Optional[str]:
        """Returns known manufacturer direct datasheet download link for a part."""
        part_clean = part_name.strip().upper()
        for pattern, url_template in MANUFACTURER_URL_PATTERNS:
            if re.match(pattern, part_clean, re.IGNORECASE):
                return url_template.format(part=part_clean, part_lower=part_clean.lower())
        return None

    def search_online_datasheet_urls(self, query: str, limit: int = 5) -> List[str]:
        """
        Dynamically searches the web for direct datasheet PDF URLs for any chip or module.
        Uses DuckDuckGo Lite (lightweight, fast HTML response).
        """
        search_query = f"{query} datasheet pdf"
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({"q": search_query}).encode("utf-8")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            links = re.findall(r'href="([^"]+)"', html)
            pdf_links = []
            for l in links:
                if "uddg=" in l:
                    m = re.search(r'uddg=([^&]+)', l)
                    if m:
                        actual = urllib.parse.unquote(m.group(1))
                        if ".pdf" in actual.lower():
                            pdf_links.append(actual)
                elif l.startswith("http") and ".pdf" in l.lower():
                    pdf_links.append(l)

            return list(dict.fromkeys(pdf_links))[:limit]
        except Exception:
            return []

    def fetch_datasheet(self, part_name: str, direct_url: Optional[str] = None) -> Optional[str]:
        """
        Fetches and caches a chip datasheet PDF locally:
        1. Checks local cache first.
        2. If direct_url is provided, downloads directly.
        3. Checks known manufacturer URL patterns.
        4. Searches the web dynamically for candidate PDF URLs and downloads the first valid one.
        Returns the absolute local path to the cached PDF.
        """
        dest_path = os.path.join(self.datasheet_dir, f"{part_name}.pdf")
        if os.path.exists(dest_path):
            return dest_path

        # Option A: direct URL
        if direct_url:
            path = self.download_datasheet_url(direct_url, part_name)
            if path:
                return path

        # Option B: manufacturer template
        cand_url = self.get_candidate_datasheet_url(part_name)
        if cand_url:
            path = self.download_datasheet_url(cand_url, part_name)
            if path:
                return path

        # Option C: dynamic web search
        candidates = self.search_online_datasheet_urls(part_name, limit=5)
        for url in candidates:
            path = self.download_datasheet_url(url, part_name)
            if path:
                return path

        return None

    def _download_text(self, url: str) -> Optional[str]:
        headers = {"User-Agent": "OhmicEngine/1.0"}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return None

    def _extract_symbol_from_library(self, lib_content: str, sym_name: str) -> Optional[str]:
        m = re.search(r'\(symbol\s+"' + re.escape(sym_name) + r'"', lib_content)
        if not m:
            return None
        start = m.start()
        depth = 0
        in_q = False
        esc = False
        for i in range(start, len(lib_content)):
            c = lib_content[i]
            if esc: esc = False; continue
            if c == '\\': esc = True; continue
            if c == '"': in_q = not in_q; continue
            if not in_q:
                if c == '(': depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        return lib_content[start:i+1]
        return None
