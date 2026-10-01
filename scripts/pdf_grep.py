"""Print every page-numbered line of a PDF that matches a regex, with context.

Used while hand-collecting the lender panel: lets a number be traced to the exact page of
the lender's own filing it was read from.

    python scripts/pdf_grep.py sources/filings/x.pdf "proforma|pro forma" [context_lines]
"""
import re
import sys

from pypdf import PdfReader


def main() -> None:
    path, pattern = sys.argv[1], re.compile(sys.argv[2], re.IGNORECASE)
    context = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    for page_no, page in enumerate(PdfReader(path).pages, start=1):
        lines = (page.extract_text() or "").splitlines()
        hits = [i for i, line in enumerate(lines) if pattern.search(line)]
        shown = set()
        for i in hits:
            for j in range(max(0, i - context), min(len(lines), i + context + 1)):
                if j not in shown:
                    shown.add(j)
                    print(f"p{page_no}: {lines[j].strip()}")
            print("  --")


if __name__ == "__main__":
    main()
