"""Downloads RBI's own press release for every Financial Stability Report edition.

RBI's FSR PDFs (rbidocs.rbi.org.in) are CAPTCHA-blocked to scripts, but the press release
for each edition is a plain web page, and it quotes the macro stress-test baseline
directly. The index page (FsReports.aspx) lists one year's editions at a time behind an
ASP.NET postback, so this replays that form once per year to collect the links.

    python scripts/fetch_rbi_fsr.py            # saves to sources/rbi/pr_<prid>.html

Writes sources/rbi/fsr_index.tsv (year, prid, title). sources/ is gitignored.
"""
from __future__ import annotations

import html
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.rbi.org.in/Scripts/"
OUT = Path(__file__).resolve().parent.parent / "sources" / "rbi"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
HIDDEN = re.compile(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"')
LINK = re.compile(r"BS_PressReleaseDisplay\.aspx\?prid=(\d+)[^>]*>([^<]*Financial Stability Report[^<]*)", re.I)


def _get(url: str, data: bytes | None = None) -> str:
    request = urllib.request.Request(url, data=data, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index_page = _get(BASE + "FsReports.aspx")
    editions: dict[str, tuple[str, str]] = {}
    for year in range(2010, 2027):
        form = {name: html.unescape(value) for name, value in HIDDEN.findall(index_page)}
        form.update({"hdnYear": str(year), "btn": "Go"})
        page = _get(BASE + "FsReports.aspx", urllib.parse.urlencode(form).encode())
        for prid, title in LINK.findall(page):
            editions.setdefault(prid, (str(year), " ".join(title.split())))
        time.sleep(1)
    rows = sorted(editions.items(), key=lambda kv: int(kv[0]))
    (OUT / "fsr_index.tsv").write_text(
        "".join(f"{year}\t{prid}\t{title}\n" for prid, (year, title) in rows), encoding="utf-8")
    for prid, (year, title) in rows:
        target = OUT / f"pr_{prid}.html"
        if not target.exists():
            target.write_text(_get(f"{BASE}BS_PressReleaseDisplay.aspx?prid={prid}"), encoding="utf-8")
            time.sleep(1)
        print(year, prid, title)


if __name__ == "__main__":
    main()
