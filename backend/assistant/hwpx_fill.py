"""
신청서 HWPX 값 자동입력 — 표 구조 인식판 (lxml).

문제 해결 이력:
  - v1 (텍스트 노드 순서): 표에서 값이 엉뚱한 칸에 들어감
  - v2 (ElementTree 재저장): 네임스페이스 15개 중 2개만 남겨 한글이 파일 거부
  - v3 (lxml 재저장): 네임스페이스 보존 → 네이티브 HWPX 는 정상 열림
       (HWP→HWPX 변환본은 hwp-convert 자체 호환성 문제로 별개)
  - v4 (문자열 치환): 빈 셀에 <hp:t> 가 아예 없으면 못 채움 → 회귀
  - v5 (이 버전, = v3 + 보강): lxml 로 tree 를 수정하되 네임스페이스를 그대로 두고,
       빈 셀엔 <hp:t> 요소를 만들어 넣는다. fwSpace 등 중간 태그가 있는 라벨도 인식.

채우는 규칙:
  1. 표(<hp:tbl>): (row,col) 격자로 라벨 셀 찾고, 오른쪽(없으면 아래) 셀에 값
  2. 표 밖: '라벨 → 이어지는 빈 <hp:t>'
  3. 서명란: '기업명 :        ' 처럼 한 <hp:t> 안 라벨+공백 → 공백에 값 삽입

팀원 원본(biz_cert_ocr.fill_hwpx)은 건드리지 않는다.
"""

import copy
import math
import os
import re
import shutil
import tempfile
import zipfile

from lxml import etree as ET

from backend.assistant.biz_cert_ocr import EXCLUDE, resolve_key, _norm

_SECTION_RE = re.compile(r"^Contents/section\d+\.xml$")
_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'

_SIGN_HINT = ("서명", "(인)", "( 인 )", "날인", "직인", "(직인)")
_AMBIGUOUS = {"공장", "본사", "본점", "지점", "계", "명", "구분", "기업", "회사", "대표", "구 분"}
_CEO_LABELS = {"대표자", "대표자명", "대표자성명", "대표이사", "성명대표자"}
_NAME_LABELS = {"성명", "성 명"}
_NAME_LABELS_RE = re.compile(r"^(성명|성함|이름)$")
_NOT_CEO_CTX = ("담당자", "담 당 자", "실무자", "실무담당", "참여자", "참여인력",
                "책임자", "기술닥터", "위원", "연구원", "종사자")
_HEAD_LABELS = {"본사", "본점", "주사무소", "본사소재지", "본점소재지", "주소본사"}


def _local(el):
    return el.tag.rpartition("}")[2] if isinstance(el.tag, str) else ""


def _kids(el, name):
    return [c for c in el if _local(c) == name]


def _in_table(el):
    return any(_local(a) == "tbl" for a in el.iterancestors())


def _text_of(el):
    """el 아래 모든 <hp:t> 텍스트. <hp:fwSpace/> 등 중간 태그 뒤 텍스트도 포함."""
    return "".join("".join(t.itertext()) for t in el.iter() if _local(t) == "t")


def _drop_linesegs(el):
    """el 아래 <hp:linesegarray> 제거 → 한글이 문단 레이아웃을 다시 계산해 새 텍스트를 표시."""
    for ls in [x for x in el.iter() if _local(x) == "linesegarray"]:
        parent = ls.getparent()
        if parent is not None:
            parent.remove(ls)


def _set_t_text(t, value):
    """<hp:t> 의 내용을 value 로 완전히 교체 (자식 태그 제거) + 문단 레이아웃 캐시 무효화."""
    for c in list(t):
        t.remove(c)
    t.text = value
    p = t.getparent()
    while p is not None and _local(p) != "p":
        p = p.getparent()
    if p is not None:
        _drop_linesegs(p)


# ── 라벨 → key 매칭 ────────────────────────────────────────────────────
def _is_prose(s):
    w = s.split()
    return len(w) >= 3 and sum(1 for x in w if len(x) >= 2) >= 2


def _resolve(label, rules, biz_type):
    k = resolve_key(label, rules, biz_type)
    if k:
        return k
    nl = _norm(label)
    if len(nl) < 2 or nl in _AMBIGUOUS:
        return None
    best = None
    for rule in rules:
        for kw in rule["keywords"]:
            nk = _norm(kw)
            if len(nk) >= 3 and nl in nk and len(nl) >= len(nk) * 0.4:
                key = rule["key"]
                if key == "trade_name" and biz_type == "법인":
                    key = "corp_name"
                elif key == "corp_name" and biz_type == "개인":
                    key = "trade_name"
                if best is None or len(nk) < best[1]:
                    best = (key, len(nk))
    return best[0] if best else None


def _match_key(label_text, rules, biz_type, row_texts=(), allow_sign=False,
               models=None, table_text=""):
    s = label_text.strip().strip(" \t:：·.")
    if not s or _is_prose(s):
        return None
    if any(ex in s.lower() for ex in EXCLUDE):
        return None
    ns = _norm(s)
    row_join = _norm(" ".join(row_texts))
    ctx_bad = any(k in (s + row_join) for k in _NOT_CEO_CTX)
    sign_bad = (not allow_sign) and any(h in (s + row_join) for h in _SIGN_HINT)

    # '본 사' / '본점' — 같은 행/맥락에 '주소·소재지'가 있으면 본사 주소 칸
    if ns in _HEAD_LABELS and ("주소" in row_join or "소재지" in row_join):
        return "address_basic"
    # '신청인(대표)' 류 = 대표자
    if "신청인" in ns and "대표" in (ns + row_join):
        return None if (ctx_bad or sign_bad) else "ceo_name"

    # 라벨에 '대표'가 들어가면(대표/대표자/대표이사/공동대표/대표 성명 …) 대표자 이름
    if "대표" in ns and ns not in _AMBIGUOUS:
        return None if (ctx_bad or sign_bad) else "ceo_name"
    if ns in _CEO_LABELS:
        return None if (ctx_bad or sign_bad) else "ceo_name"

    # '성명 / 이름' 처럼 문맥 의존 라벨 — LangChain(로컬 Qwen) 이 표 문맥 보고 판별,
    # 같은 행에 '대표'가 있으면 LLM 없이 확정. (models 없으면 폴백)
    if ns in _NAME_LABELS or _NAME_LABELS_RE.match(ns):
        if ctx_bad or sign_bad:
            return None
        if "대표" in row_join:
            return "ceo_name"
        try:
            from backend.assistant.label_llm import is_ceo_label
            ctx = (" ".join(row_texts) + " " + table_text).strip()
            if is_ceo_label(s, ctx, models) is True:
                return "ceo_name"
        except Exception:
            pass
        return None

    return _resolve(s, rules, biz_type)


# ── 표 파싱 ────────────────────────────────────────────────────────────
def _parse_table(tbl):
    cells = {}
    for tr in _kids(tbl, "tr"):
        for tc in _kids(tr, "tc"):
            ca = _kids(tc, "cellAddr")
            if not ca:
                continue
            row, col = int(ca[0].get("rowAddr")), int(ca[0].get("colAddr"))
            cs = _kids(tc, "cellSpan")
            rs_n = int(cs[0].get("rowSpan")) if cs else 1
            cs_n = int(cs[0].get("colSpan")) if cs else 1
            cells[(row, col)] = {"tc": tc, "rs": rs_n, "cs": cs_n}
    return cells


def _cell_first_p(tc):
    for sub in _kids(tc, "subList"):
        ps = _kids(sub, "p")
        if ps:
            return ps[0]
    return None


def _cell_empty(tc):
    return _text_of(tc).strip() == ""


_ONLY_MARKER = re.compile(r"^\(?\s*(?:서명\s*(?:또는\s*인)?|인|직인|날인|印)\s*\)?$")
_SIGN_CO = {"기업명", "업체명", "상호", "법인명", "회사명"}


def _sign_label_key(label_text, biz_type, row_texts=()):
    """'대표자 :' '기업명 :' 처럼 콜론으로 끝나는 서명 라벨 → key (그 외 None)."""
    s = label_text.strip()
    if not s.endswith((":", "：")):
        return None
    row_join = _norm(" ".join(row_texts))
    if any(k in (_norm(s) + row_join) for k in _NOT_CEO_CTX):
        return None
    ns = _norm(s.strip(" :："))
    if "대표" in ns and ns not in _AMBIGUOUS:
        return "ceo_name"
    if ns in _SIGN_CO:
        return "corp_name" if biz_type == "법인" else "trade_name"
    return None


def _prepend_cell(tc, value):
    """셀 첫 문단 첫 <hp:t> 앞에 값을 끼워 넣는다 ('(인)' 만 있는 서명칸용). 쓴 run 반환."""
    p = _cell_first_p(tc)
    if p is None:
        return None
    for run in _kids(p, "run"):
        ts = _kids(run, "t")
        if ts:
            _set_t_text(ts[0], value + "".join(ts[0].itertext()))
            return run
    return None


def _write_cell(tc, value):
    """값 칸 첫 문단 첫 run 의 <hp:t> 에 값. run/<hp:t> 없으면 만든다. 쓴 run 반환(실패 시 None)."""
    p = _cell_first_p(tc)
    if p is None:
        return None
    ns = p.tag[: p.tag.index("}") + 1]
    runs = _kids(p, "run")
    if not runs:
        run = ET.SubElement(p, ns + "run")
        p.insert(0, run)
    else:
        run = runs[0]
    ts = _kids(run, "t")
    if ts:
        _set_t_text(ts[0], value)
    else:
        t = ET.SubElement(run, ns + "t")
        run.insert(0, t)
        t.text = value
        _drop_linesegs(p)
    return run


# ── 채우기 ─────────────────────────────────────────────────────────────
def _is_roster(tbl_text):
    """참여인력/서명 명단 표 — 여기의 '대표자'·'성명'은 우리 대표가 아님."""
    return (("역할" in tbl_text or "직위" in tbl_text)
            and ("서명" in tbl_text or "자필" in tbl_text or "참여" in tbl_text))


def _fill_tables(root, rules, biz_cert, biz_type, log, section, models=None, written=None):
    for tbl in [e for e in root.iter() if _local(e) == "tbl"]:
        cells = _parse_table(tbl)
        tbl_text = _text_of(tbl)
        roster = _is_roster(tbl_text)
        by_row = {}
        for (r, _c), cc in cells.items():          # rowSpan 만큼 아래 행에도 라벨 반영
            txt = _text_of(cc["tc"])
            for rr in range(r, r + max(1, cc.get("rs", 1))):
                by_row.setdefault(rr, []).append(txt)
        for (row, col), c in cells.items():
            tc = c["tc"]
            if any(_local(x) == "tbl" for x in tc.iter() if x is not tc):
                continue
            ltxt = _text_of(tc)
            key = _match_key(ltxt, rules, biz_type, by_row.get(row, ()),
                             models=models, table_text=tbl_text)
            if not key:
                key = _sign_label_key(ltxt, biz_type, by_row.get(row, ()))   # '대표자:' 옆 '(인)'
            if not key or not biz_cert.get(key):
                continue
            if roster and key == "ceo_name":
                continue
            val = biz_cert[key]
            for pos in [(row, col + c["cs"]), (row + c["rs"], col)]:
                tgt = cells.get(pos)
                if not tgt:
                    continue
                ttxt = _text_of(tgt["tc"]).strip()
                run = None
                if ttxt == "":
                    run = _write_cell(tgt["tc"], val)
                elif key in ("ceo_name", "corp_name", "trade_name") and _ONLY_MARKER.match(ttxt):
                    run = _prepend_cell(tgt["tc"], val + "   ")   # (인) 만 있는 서명칸
                if run is not None:
                    log.append((section, _text_of(tc).strip(), val))
                    if written is not None:
                        written.append((run, val))
                    break
                if ttxt == "":
                    break


def _fill_flow(root, rules, biz_cert, biz_type, log, section, models=None, written=None):
    ts = [t for t in root.iter() if _local(t) == "t" and not _in_table(t)]
    pending = None
    for t in ts:
        s = "".join(t.itertext()).strip().strip(" \t:：·.")
        if pending is not None and s == "":
            _set_t_text(t, pending[1])
            log.append((section, pending[0], pending[1]))
            if written is not None and _local(t.getparent()) == "run":
                written.append((t.getparent(), pending[1]))
            pending = None
            continue
        if not s:
            continue
        key = _match_key(s, rules, biz_type, allow_sign=True, models=models)
        if key and biz_cert.get(key):
            pending = (s, biz_cert[key])
        elif len(s) >= 4:
            pending = None


# 서명/맺음말 라벨. '신청인'은 바로 뒤 '(대표)' 표기가 있을 때만 (신청인=대표 단정 금지).
_CO_AT = re.compile(
    r"(?:기\s*업\s*명|업\s*체\s*명|상\s*호|법\s*인\s*명|회\s*사\s*명|신\s*청\s*기\s*업)(?:[ 　]*[:：])?")
_CEO_AT = re.compile(
    r"(?:대\s*표\s*자(?:\s*성\s*명)?|대\s*표\s*이\s*사|신\s*청\s*인\s*\(\s*대\s*표\s*\))(?:[ 　]*[:：])?")

# '이 자리는 서명란' 임을 알려주는 토큰 — 표 안에서는 이게 있어야만 문장형 채우기 허용
_SIGN_TOKENS = ("(인)", "( 인 )", "( 인)", "(인 )", "(직인)", "( 직인 )",
                "서명", "날인", "(서명", "또는 인", "(印)")
_MARKER_RE = re.compile(r"^([ 　]*)(\([^()]{0,10}(?:인|서명|직인|印)[^()]{0,10}\))\s*$")


def _pad(val, blank=""):
    """값 앞뒤 최소 여백. (원래 공백/밑줄 폭을 값 길이에 맞춰 줄임 → 줄바꿈 방지)"""
    return " " + val + "  "


def _sign_row_p(p):
    for a in p.iterancestors():
        if _local(a) == "tr":
            return any(tok in _text_of(a) for tok in _SIGN_TOKENS)
    return False


def _fill_inline(root, biz_cert, log, section, written=None):
    """서명/맺음말의 '기업명 : ___', '대표자 : ___ (인)' 자리에 값을 넣는다.

    값을 넣는 위치 우선순위:
      1) 라벨 뒤가 밑줄(빈칸) run → 그 run 안에 (밑줄 위에 보이도록)
      2) 라벨 뒤 같은 run 의 공백 꼬리 → 거기
      3) 라벨 뒤 공백 + '(인)' 같은 표식 → 공백 자리에, 표식은 그대로
      4) 라벨 뒤 공백 + '/' 등 구분자 → 공백 자리에 (라벨에 콜론 있을 때만)
      5) 그 외 → 라벨 바로 뒤에 이어붙임
    표 안이면 같은 행에 (인)/서명 류가 있을 때만 (참여자 명단 오채움 방지).
    """
    company = biz_cert.get("corp_name") or biz_cert.get("trade_name")
    ceo = biz_cert.get("ceo_name")
    targets = []
    if company:
        targets.append((_CO_AT, company, "기업명"))
    if ceo:
        targets.append((_CEO_AT, ceo, "대표자"))
    if not targets:
        return

    for p in [x for x in root.iter() if _local(x) == "p"]:
        in_tbl = _in_table(p)
        if in_tbl and not _sign_row_p(p):
            continue
        runs = [r for r in p if _local(r) == "run"]
        ts = [t for r in runs for t in _kids(r, "t")]
        if not ts:
            continue
        texts = ["".join(t.itertext()) for t in ts]
        for i in range(len(ts)):
            if not texts[i]:
                continue
            for rx, val, tag in targets:
                m = _label_end(rx, texts[i])
                if m is None:
                    continue
                head, after = texts[i][:m], texts[i][m:]
                tgt = _place_inline(ts, texts, i, head, after, val, allow_append=not in_tbl)
                if tgt is not None:
                    log.append((section, f"서명란({tag})", val))
                    if written is not None and _local(tgt.getparent()) == "run":
                        written.append((tgt.getparent(), val))
                    texts = ["".join(t.itertext()) for t in ts]
                    break


def _label_end(rx, txt):
    """txt 안에서 '라벨(:)' 이 끝나는 위치. 라벨이 문장 중간 단어면(뒤에 글자) None."""
    for m in rx.finditer(txt):
        if m.start() > 0 and txt[m.start() - 1] not in " 　([/\t":
            continue
        rest = txt[m.end():]
        if rest == "" or rest[0] in " 　([" or _MARKER_RE.match(rest):
            return m.end()
    return None


def _place_inline(ts, texts, i, head, after, val, allow_append=True):
    """값을 넣고, 값이 들어간 <hp:t> 를 반환. 못 넣으면 None.

    allow_append=False (표 안) 이면 '라벨 바로 뒤 이어붙임'(5)은 안 한다
    — 옆 칸이 값칸일 수 있어 _fill_tables 에 맡긴다.
    """
    only_ws = after.strip("　 \t") == ""
    has_colon = ":" in head or "：" in head
    mk = _MARKER_RE.match(after)
    if only_ws and len(after) >= 3:                       # 1·2) 같은 run 공백꼬리
        _set_t_text(ts[i], head + _pad(val, after))
        return ts[i]
    if mk:                                                # 3) 공백 + (인)
        blank, marker = mk.group(1), mk.group(2)
        _set_t_text(ts[i], head + _pad(val, blank if len(blank) >= 3 else "      ") + marker)
        return ts[i]
    if only_ws and i + 1 < len(ts):                       # 1) 다음 run 이 밑줄 빈칸
        nxt = texts[i + 1]
        if nxt.strip("　 \t") == "" and len(nxt) >= 2:
            _set_t_text(ts[i + 1], _pad(val, nxt))
            return ts[i + 1]
        if _MARKER_RE.match(nxt):
            _set_t_text(ts[i], head + " " + val + "   ")
            return ts[i]
    if has_colon:
        m2 = re.match(r"^([ 　]{3,})(\S.*)$", after, re.DOTALL)   # 4) 공백 + 구분자/뒷내용
        if m2:
            _set_t_text(ts[i], head + _pad(val, m2.group(1)) + m2.group(2))
            return ts[i]
        if only_ws and allow_append:                      # 5) 이어붙임 (표 밖만)
            _set_t_text(ts[i], head + " " + val)
            return ts[i]
    return None


def _relax_pagebreak(root, biz_cert):
    """값을 채운 '큰 표'가 pageBreak=NONE 이면 CELL 로 완화.

    긴 주소 등으로 표가 커지면 '표를 나누지 않음' 규칙 탓에 표 전체가 다음 장으로
    통째로 밀려 첫 장에 제목만 남는다. 페이지 경계에서 표가 나뉘도록 허용한다.
    """
    vals = [str(v) for v in biz_cert.values() if v and len(str(v)) >= 4]
    for tbl in [e for e in root.iter() if _local(e) == "tbl"]:
        if tbl.get("pageBreak") != "NONE":
            continue
        try:
            if int(tbl.get("rowCnt", "0")) < 10:
                continue
        except ValueError:
            continue
        txt = _text_of(tbl)
        if any(v in txt for v in vals):
            tbl.set("pageBreak", "CELL")
            if tbl.get("repeatHeader") == "1":
                tbl.set("repeatHeader", "0")


_MIN_H = 1100   # 이보다 작게는 안 줄임 (11pt) — 그래도 넘치면 줄바꿈 허용


def _trim_padding(p, keep_lead=6):
    """문단 안 <hp:t> 의 과도한 연속 공백을 줄인다 (폰트 축소보다 먼저 — 사용자 요청).

    양식이 오른쪽 정렬용으로 넣어둔 수십 칸 공백이 줄바꿈을 유발하므로,
    앞쪽 대량 공백은 keep_lead 칸, 중간 대량 공백은 4칸으로 압축한다.
    """
    changed = False
    for t in [x for x in p.iter() if _local(x) == "t"]:
        if len(list(t)):                       # fwSpace 등 자식 있으면 손대지 않음
            continue
        s = t.text or ""
        if "     " not in s:                   # 5칸 이상 연속 공백 없음
            continue
        ns = re.sub(r"^ {%d,}" % (keep_lead + 1), " " * keep_lead, s)
        ns = re.sub(r" {5,}", "    ", ns)
        if ns != s:
            t.text = ns
            changed = True
    return changed


def _autofit_long_cells(charprops, next_id_box, runs):
    """값을 채운 표 셀에서 텍스트가 칸을 넘칠 것 같으면 (1) 과도한 공백 축소,
    (2) 그래도 넘치면 폰트 축소(11pt 하한).

    runs: (값을 채운 run, 값) 목록
    """
    if charprops is None or not runs:
        return
    cp_by_id = {c.get("id"): c for c in charprops if _local(c) == "charPr"}
    shrunk = {}

    def _shrunk_id(cid, target):
        cp = cp_by_id.get(cid)
        if cp is None:
            return None
        h = int(cp.get("height", "1000") or 1000)
        if target >= h - 30:
            return None
        key = (cid, target)
        if key not in shrunk:
            new = copy.deepcopy(cp)
            nid = str(next_id_box[0])
            next_id_box[0] += 1
            new.set("id", nid)
            new.set("height", str(max(700, target)))
            for sub in new:
                if _local(sub) == "ratio":
                    for a in list(sub.attrib):
                        sub.set(a, "92")
            charprops.append(new)
            charprops.set("itemCnt", str(sum(1 for c in charprops if _local(c) == "charPr")))
            shrunk[key] = nid
        return shrunk[key]

    for run, value in runs:
        ts = _kids(run, "t")
        if not ts:
            continue
        tc = next((a for a in run.iterancestors() if _local(a) == "tc"), None)
        p = next((a for a in run.iterancestors() if _local(a) == "p"), None)
        if tc is None or p is None:
            continue
        cs = _kids(tc, "cellSz")
        if not cs:
            continue
        width = int(cs[0].get("width", "0") or 0)
        if width <= 0:
            continue
        own = "".join(ts[0].itertext()).strip()
        ptext = _text_of(p).rstrip()
        pruns = [r for r in _kids(p, "run") if r.get("charPrIDRef") in cp_by_id]
        if not pruns:
            continue
        maxh = max(int(cp_by_id[r.get("charPrIDRef")].get("height", "1000") or 1000) for r in pruns)

        avail = width - 300
        if own == value.strip() and len(value) >= 18:        # 값 전용 칸(주소 등)
            # 현재 폰트로 4줄 넘게 차지할 때만 축소 (그 외는 표 페이지분할에 맡김), 11pt 하한
            cur_lines = math.ceil(len(value) / max(1, avail // maxh))
            if cur_lines > 4:
                per_line = max(6, math.ceil(len(value) / 4))
                nid = _shrunk_id(run.get("charPrIDRef"), max(_MIN_H, avail // per_line))
                if nid:
                    run.set("charPrIDRef", nid)
        else:                                                # 서명란 한 줄
            _trim_padding(p)                                 # 1) 먼저 공백 줄이기
            line = len(_text_of(p).rstrip())
            if line * maxh > avail:                          # 2) 그래도 넘치면 폰트
                nid_ok = _shrunk_id(pruns[0].get("charPrIDRef"), max(_MIN_H, avail // (line + 1)))
                if nid_ok:
                    for r in pruns:
                        nid = _shrunk_id(r.get("charPrIDRef"), max(_MIN_H, avail // (line + 1)))
                        if nid:
                            r.set("charPrIDRef", nid)


# ── 진입점 ────────────────────────────────────────────────────────────
def fill_hwpx_all(form_path, out_path, rules, biz_cert, biz_type, models=None):
    """HWPX 표/문단을 인식해 값 채우고 out_path 저장. (섹션,라벨,값) 로그 반환.

    lxml 로 tree 를 수정 → 원본 네임스페이스 선언 15개를 그대로 보존해 재저장한다.
    models=(Qwen model, processor) 를 넘기면 '대표자' 계열 라벨 판별에 LangChain 체인 사용
    (없으면 키워드 규칙만).
    """
    work = tempfile.mkdtemp(prefix="hwpxfill_")
    try:
        with zipfile.ZipFile(form_path) as z:
            names = z.namelist()
            z.extractall(work)

        # header.xml (charPr 정의) — 긴 값 폰트 축소용
        hdr_path = os.path.join(work, "Contents", "header.xml")
        hdr_root = charprops = None
        next_id_box = [1]
        if os.path.exists(hdr_path):
            with open(hdr_path, "rb") as f:
                hdr_root = ET.fromstring(f.read())
            charprops = next((e for e in hdr_root.iter() if _local(e) == "charProperties"), None)
            if charprops is not None:
                ids = [int(c.get("id")) for c in charprops
                       if _local(c) == "charPr" and (c.get("id") or "").isdigit()]
                next_id_box = [max(ids, default=0) + 1]

        log = []
        written = []
        sec_roots = []
        for rel in sorted(n for n in names if _SECTION_RE.match(n)):
            path = os.path.join(work, *rel.split("/"))
            with open(path, "rb") as f:
                raw = f.read()
            root = ET.fromstring(raw)
            sec = os.path.basename(rel)
            _fill_tables(root, rules, biz_cert, biz_type, log, sec, models, written)
            _fill_inline(root, biz_cert, log, sec, written)   # 서명란(한 노드 안 공백) 먼저
            _fill_flow(root, rules, biz_cert, biz_type, log, sec, models, written)  # '라벨→빈 노드'
            _relax_pagebreak(root, biz_cert)
            sec_roots.append((path, root))

        _autofit_long_cells(charprops, next_id_box, written)
        for path, root in sec_roots:
            body = ET.tostring(root, encoding="unicode")
            with open(path, "w", encoding="utf-8") as f:
                f.write(_XML_DECL + body)
        if hdr_root is not None:
            with open(hdr_path, "w", encoding="utf-8") as f:
                f.write(_XML_DECL + ET.tostring(hdr_root, encoding="unicode"))

        if os.path.exists(out_path):
            os.remove(out_path)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            mt = os.path.join(work, "mimetype")
            if os.path.exists(mt):
                z.write(mt, "mimetype", compress_type=zipfile.ZIP_STORED)
            for r, _d, files in os.walk(work):
                for fn in files:
                    full = os.path.join(r, fn)
                    arc = os.path.relpath(full, work).replace(os.sep, "/")
                    if arc != "mimetype":
                        z.write(full, arc)
        return log
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    import sys

    from backend.assistant.pipeline import _load_mapping, _record_to_biz_cert

    if len(sys.argv) < 4:
        print("usage: python -m backend.assistant.hwpx_fill <form.hwpx> <mapping.xlsx> <out.hwpx>")
        sys.exit(1)
    form, xlsx, out = sys.argv[1:4]
    rec = {
        "entity_type": "법인", "trade_name": "", "corp_name": "(주)테스트테크",
        "ceo_name": "김철수", "biz_no": "124-81-00455", "corp_no": "110111-0734560",
        "birth_date": "", "open_date": "2019-07-10",
        "address_basic": "서울특별시 서초구 강남대로 456, 7층",
        "business_category": [{"업태": "정보통신업", "종목": ["소프트웨어 개발"]}],
    }
    bc, ent = _record_to_biz_cert(rec)
    log = fill_hwpx_all(form, out, _load_mapping(xlsx), bc, ent)
    print(f"채운 필드 {len(log)}개:")
    for s, fld, val in log:
        print(f"  [{s}] {fld!r} <- {val}")
    print(f"-> {out}")
