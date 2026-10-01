"""Print every sentence of a saved HTML page that matches a regex.

Companion to pdf_grep.py, for sources published as web pages (RBI press releases and
Financial Stability Report chapters, SEC 6-K filings).

    python scripts/html_grep.py sources/rbi/pr_44305.html "GNPA|gross non-performing"
"""
import html
import re
import sys


def page_text(path: str) -> str:
    raw = open(path, encoding="utf-8", errors="replace").read()
    raw = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def main() -> None:
    text, pattern = page_text(sys.argv[1]), re.compile(sys.argv[2], re.IGNORECASE)
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 450
    title = re.search(r"<title>(.*?)</title>", open(sys.argv[1], encoding="utf-8", errors="replace").read(), re.S)
    print("TITLE:", title.group(1).strip() if title else "?")
    # A sentence ends at a full stop that is not a decimal point.
    for sentence in re.split(r"(?<=[a-z\)%])\.\s+(?=[A-Z])", text):
        if pattern.search(sentence):
            print("-", sentence.strip()[:width])


if __name__ == "__main__":
    main()
