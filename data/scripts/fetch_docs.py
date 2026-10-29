#!/usr/bin/env python3
"""
fetch_docs.py — Download real public transit & aggregator policy documents (VERIFIED and UNVERIFIED).
Extracts clean text and metadata, and generates SHA-256 checksums.
"""

import hashlib
import json
import os
import re
import ssl
import sys
import urllib.request
from pathlib import Path

import bs4
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SOURCES_YAML = PROJECT_ROOT / "data" / "sources.yaml"
RAW_DOCS_DIR = PROJECT_ROOT / "data" / "raw" / "docs"
CHECKSUM_FILE = PROJECT_ROOT / "data" / "checksums.json"

# Bypass state government self-signed/local CA issues on Karnataka portals
SSL_CONTEXT = ssl._create_unverified_context()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
}


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_html(html_bytes: bytes) -> str:
    soup = bs4.BeautifulSoup(html_bytes, "html.parser")
    # Remove script, style, nav, footer, header
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()

    # Prefer main article container if present
    main_content = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", {"id": re.compile(r"content|main|article|body", re.I)})
        or soup.find("div", {"class": re.compile(r"content|main|article|story|post", re.I)})
        or soup.body
        or soup
    )

    lines = []
    for elem in main_content.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th"]):
        text = elem.get_text(separator=" ", strip=True)
        if len(text) > 20:
            if elem.name in ["h1", "h2", "h3", "h4"]:
                lines.append(f"\n### {text}\n")
            else:
                lines.append(text)

    clean_text = "\n\n".join(lines)
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
    return clean_text


def extract_pdf(pdf_bytes: bytes) -> str:
    import io
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            extracted.append(f"--- [Page {idx + 1}] ---\n{text.strip()}")
    return "\n\n".join(extracted)


def fetch_all():
    if not SOURCES_YAML.exists():
        print(f"ERROR: {SOURCES_YAML} not found!", file=sys.stderr)
        sys.exit(1)

    RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    with open(SOURCES_YAML, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sources = config.get("sources", [])
    print(f"Found {len(sources)} sources in {SOURCES_YAML.name}")

    checksums = {}
    if CHECKSUM_FILE.exists():
        try:
            with open(CHECKSUM_FILE, "r") as f:
                checksums = json.load(f)
        except Exception:
            checksums = {}

    summary = []

    for src in sources:
        doc_id = src["id"]
        url = src["url"]
        tier = src["trust_tier"]
        doc_type = src.get("doc_type", "html")
        title = src.get("title", doc_id)

        print(f"\n[{tier}] Fetching: {doc_id} ({url})...")
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=25) as resp:
                raw_bytes = resp.read()

            sha256 = compute_sha256(raw_bytes)
            raw_size = len(raw_bytes)

            if doc_type == "pdf":
                text = extract_pdf(raw_bytes)
            else:
                text = clean_html(raw_bytes)

            # If clean_html returned very little text, fallback to raw soup string
            if len(text.strip()) < 100:
                soup = bs4.BeautifulSoup(raw_bytes, "html.parser")
                text = soup.get_text(separator="\n", strip=True)

            text_path = RAW_DOCS_DIR / f"{doc_id}.txt"
            meta_path = RAW_DOCS_DIR / f"{doc_id}.json"

            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text)

            meta = dict(src)
            meta["raw_sha256"] = sha256
            meta["raw_bytes"] = raw_size
            meta["extracted_chars"] = len(text)
            meta["extracted_words"] = len(text.split())

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            checksums[f"docs/{doc_id}"] = {
                "sha256": sha256,
                "bytes": raw_size,
                "words": meta["extracted_words"],
                "trust_tier": tier,
                "url": url,
            }

            summary.append(meta)
            print(f"  -> Saved {meta['extracted_words']} words ({meta['extracted_chars']} chars) to {text_path.name}")

        except Exception as e:
            print(f"  ERROR fetching {doc_id}: {e}", file=sys.stderr)

    with open(CHECKSUM_FILE, "w", encoding="utf-8") as f:
        json.dump(checksums, f, indent=2)

    # Save corpus summary
    corpus_summary_file = RAW_DOCS_DIR / "corpus_summary.json"
    with open(corpus_summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    v_count = sum(1 for s in summary if s["trust_tier"] == "VERIFIED")
    u_count = sum(1 for s in summary if s["trust_tier"] == "UNVERIFIED")
    print(f"\nCompleted corpus download: {v_count} VERIFIED documents, {u_count} UNVERIFIED documents.")
    print(f"Checksums recorded in {CHECKSUM_FILE}")


if __name__ == "__main__":
    fetch_all()
