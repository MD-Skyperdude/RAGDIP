"""
validate_filenames.py
Validates all documents (PDF, DOCX, XLSX, PPTX) before ingestion.

Usage:
    python validate_filenames.py --dir ./synthetic_pdfs
    python validate_filenames.py --dir ./real_docs      # on Wednesday
"""

import os
import re
import argparse
from datetime import datetime

VALID_ASSET_CLASSES = {"RE", "PE", "PC", "SEC", "VC", "OPP"}
VALID_DOC_TYPES     = {"Notes", "Marketing"}
VALID_EXTENSIONS    = {".pdf", ".docx", ".xlsx", ".pptx"}

ASSET_CLASS_LABELS  = {
    "RE":  "Real Estate (Real Assets)",
    "PE":  "Private Equity",
    "PC":  "Private Credit",
    "SEC": "Secondaries",
    "VC":  "Venture Capital",
    "OPP": "Uncorrelated",
}

EXT_LABELS = {
    ".pdf":  "PDF Document",
    ".docx": "Word Document",
    ".xlsx": "Excel Spreadsheet",
    ".pptx": "PowerPoint Presentation",
}

# Matches: AssetClass.Manager.DocType.YYYYMMDD[( N)].ext
PATTERN = re.compile(
    r'^([A-Z]+)\.'
    r'([A-Za-z0-9]+)\.'
    r'(Notes|Marketing)\.'
    r'(\d{8})'
    r'(?: \((\d+)\))?'
    r'\.(pdf|docx|xlsx|pptx)$',
    re.IGNORECASE
)

def parse_filename(filename):
    m = PATTERN.match(filename)
    if not m:
        raise ValueError("Does not match: AssetClass.Manager.DocType.YYYYMMDD[( N)].(pdf|docx|xlsx|pptx)")

    asset_class  = m.group(1).upper()
    manager_name = m.group(2)
    doc_type     = m.group(3).capitalize()
    date_str     = m.group(4)
    duplicate_n  = m.group(5)
    extension    = "." + m.group(6).lower()

    if asset_class not in VALID_ASSET_CLASSES:
        raise ValueError(f"Unknown asset class '{asset_class}'. Valid: {', '.join(sorted(VALID_ASSET_CLASSES))}")
    if doc_type not in VALID_DOC_TYPES:
        raise ValueError(f"Unknown doc type '{doc_type}'. Valid: Notes, Marketing")

    try:
        parsed_date = datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise ValueError(f"Invalid date '{date_str}'. Expected YYYYMMDD.")

    return {
        "filename":     filename,
        "asset_class":  asset_class,
        "asset_label":  ASSET_CLASS_LABELS[asset_class],
        "manager_name": manager_name,
        "doc_type":     doc_type,
        "doc_date":     parsed_date,
        "extension":    extension,
        "duplicate_n":  int(duplicate_n) if duplicate_n else None,
        "base_name":    f"{asset_class}.{manager_name}.{doc_type}.{date_str}",
    }

def validate_directory(pdf_dir):
    all_files = os.listdir(pdf_dir)
    files = [f for f in all_files
             if os.path.splitext(f)[1].lower() in VALID_EXTENSIONS]

    skipped_ext = [f for f in all_files
                   if f not in files and not f.startswith(".")]

    if not files:
        print(f"No supported documents found in {pdf_dir}")
        return

    print(f"\nScanning {len(files)} documents in: {pdf_dir}")
    if skipped_ext:
        print(f"  (Skipping {len(skipped_ext)} unsupported file types)")
    print("=" * 70)

    valid   = []
    invalid = []

    for filename in sorted(files):
        try:
            valid.append(parse_filename(filename))
        except ValueError as e:
            invalid.append({"filename": filename, "reason": str(e)})

    if invalid:
        print(f"\n❌  INVALID FILES ({len(invalid)}) — fix before ingestion:\n")
        for item in invalid:
            print(f"  FILE:   {item['filename']}")
            print(f"  REASON: {item['reason']}\n")
    else:
        print("\n✅  All filenames valid — no issues found.")

    print(f"\n{'─' * 70}")
    print("SUMMARY")
    print(f"{'─' * 70}")
    print(f"  Total scanned   : {len(files)}")
    print(f"  Valid           : {len(valid)}")
    print(f"  Invalid         : {len(invalid)}")

    if valid:
        print(f"\n  By asset class:")
        ac = {}
        for v in valid:
            label = f"{v['asset_class']} ({v['asset_label']})"
            ac[label] = ac.get(label, 0) + 1
        for label, count in sorted(ac.items()):
            print(f"    {label:<38} {count:>4} files")

        print(f"\n  By doc type:")
        dt = {}
        for v in valid:
            dt[v['doc_type']] = dt.get(v['doc_type'], 0) + 1
        for dtype, count in sorted(dt.items()):
            print(f"    {dtype:<38} {count:>4} files")

        print(f"\n  By file type:")
        ft = {}
        for v in valid:
            label = EXT_LABELS.get(v['extension'], v['extension'])
            ft[label] = ft.get(label, 0) + 1
        for ftype, count in sorted(ft.items()):
            print(f"    {ftype:<38} {count:>4} files")

        dates = [v['doc_date'] for v in valid]
        print(f"\n  Date range: {min(dates)} → {max(dates)}")

        dups = [v for v in valid if v['duplicate_n'] is not None]
        if dups:
            print(f"\n  Duplicate copies: {len(dups)}")
            bc = {}
            for d in dups:
                bc[d['base_name']] = bc.get(d['base_name'], 0) + 1
            for base, count in sorted(bc.items()):
                print(f"    {base}  →  {count + 1} total copies")
        else:
            print(f"\n  No duplicate copies found.")

    print(f"\n{'=' * 70}")
    if invalid:
        print(f"\n⚠️   Fix {len(invalid)} invalid file(s), then re-run this script.")
    else:
        print(f"\n✅  Ready to ingest. Run: python phase1_ingest.py --dir {pdf_dir}\n")

    return valid, invalid

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Path to documents directory")
    args = parser.parse_args()
    validate_directory(args.dir)
