# HWPX(신버전 한글) 원문을 읽기 전용 HTML로 변환 - "원본 공고문 보기" iframe용.
# 표는 <hp:p> 안에 중첩되어 있어(형제가 아님) 표를 먼저 확인하고, 없을 때만 문단 텍스트로 처리한다.

import html
import zipfile
from io import BytesIO

from lxml import etree as ET

from backend.assistant.hwpx_fill import _SECTION_RE, _local, _parse_table, _text_of


def _render_table(tbl):
    cells = _parse_table(tbl)
    if not cells:
        return ""
    max_row = max(r for r, _c in cells)
    max_col = max(c for _r, c in cells)
    occupied = set()
    rows_html = []
    for r in range(max_row + 1):
        row_cells = []
        for c in range(max_col + 1):
            if (r, c) in occupied:
                continue
            cell = cells.get((r, c))
            if cell is None:
                continue
            rs, cs = cell["rs"], cell["cs"]
            for rr in range(r, r + rs):
                for cc in range(c, c + cs):
                    occupied.add((rr, cc))
            attrs = (f' rowspan="{rs}"' if rs > 1 else "") + (f' colspan="{cs}"' if cs > 1 else "")
            text = html.escape(_text_of(cell["tc"]).strip()).replace("\n", "<br>")
            row_cells.append(f"<td{attrs}>{text}</td>")
        if row_cells:
            rows_html.append(f"<tr>{''.join(row_cells)}</tr>")
    return f"<table>{''.join(rows_html)}</table>"


def _render_section(root):
    parts = []
    for p in [e for e in root if _local(e) == "p"]:
        tbl = next((d for d in p.iterdescendants() if _local(d) == "tbl"), None)
        if tbl is not None:
            parts.append(_render_table(tbl))
            continue
        text = _text_of(p).strip()
        if text:
            parts.append(f"<p>{html.escape(text)}</p>")
    return "".join(parts)


_STYLE = """
body { font-family: -apple-system, "Malgun Gothic", sans-serif; padding: 16px; line-height: 1.6; }
p { margin: 4px 0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
td { border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }
"""


def hwpx_to_html(file_bytes: bytes) -> str:
    """HWPX(zip) 바이트 -> 렌더링된 HTML 문자열. 파싱 실패 시 예외를 던진다(호출측이 다운로드로 폴백)."""
    body = []
    with zipfile.ZipFile(BytesIO(file_bytes)) as z:
        for name in sorted(n for n in z.namelist() if _SECTION_RE.match(n)):
            root = ET.fromstring(z.read(name))
            body.append(_render_section(root))
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{_STYLE}</style></head><body>{''.join(body)}</body></html>"
