"""
사업자등록증의 '사업의 종류'(업태·종목) 추출 — EasyOCR + 좌표 규칙 기반.

Qwen VLM은 이 표에서 행을 빠뜨리거나 라벨/값을 헷갈려서, 이 부분만 별도로
EasyOCR(글자+박스좌표)로 읽고 기하 규칙으로 업태-종목을 묶는다.

파이프라인: prep → (저화질이면 대비강화) → EasyOCR → '사업의 종류' 영역 추출
         → 업태/종목 칼럼 분리 → 줄 병합(접힌 값) → y밴드 그룹핑

반환: [{"업태": str, "종목": [str, ...]}]
"""

import difflib
import re

_READER = None

_QWEN_TEXT_PROMPT = (
    "이 사업자등록증의 '사업의 종류' 항목을 읽어라. 왼쪽 '업태' 칸, 오른쪽 '종목' 칸이 있다.\n"
    "규칙:\n"
    "1. '업태','종목' 이라는 칸 제목 글자는 값이 아니다. 제외.\n"
    "2. 각 칸의 값을 위에서 아래 순서대로 하나도 빠짐없이 모두 읽어라.\n"
    "3. 한 줄 안에 쉼표(,)나 가운뎃점(·)으로 여러 개가 적혀 있어도 나누지 말고 그 줄 전체를 한 값으로.\n"
    "4. 한 값이 두 줄로 접혀 있으면 작은 글씨까지 빠짐없이 읽어 하나로 이어붙여라.\n"
    "5. 한글로만. 한자 금지.\n"
    "아래 JSON만 출력:\n"
    '{"업태목록": ["행1", "행2"], "종목목록": ["행1", "행2"]}'
)


def get_reader():
    global _READER
    if _READER is None:
        import easyocr

        _READER = easyocr.Reader(["ko", "en"], gpu=True, verbose=False)
    return _READER


def _prep(path_or_im, max_side=2600):
    from PIL import Image, ImageOps

    im = path_or_im if hasattr(path_or_im, "size") else Image.open(path_or_im)
    im = ImageOps.exif_transpose(im)
    if im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    if max(w, h) > max_side:
        s = max_side / max(w, h)
        im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    return im


def _enhance(im):
    """저화질 대응: 그레이스케일 + CLAHE 대비강화 + 샤픈."""
    import cv2
    import numpy as np

    g = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2GRAY)
    g = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(g)
    g = cv2.filter2D(g, -1, np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]))
    return cv2.cvtColor(g, cv2.COLOR_GRAY2RGB)


def _cx(b):
    return sum(p[0] for p in b) / 4


def _cy(b):
    return sum(p[1] for p in b) / 4


def _despace(s):
    return re.sub(r"\s+", "", s)


def _ocr(im):
    import numpy as np

    return get_reader().readtext(np.array(im), detail=1, paragraph=False)


_ANCHOR_RE = re.compile(r"사?업?의?종류|^종류$")


def _is_anchor(t):
    dt = _despace(t)
    return ("종류" in dt and "등록" not in dt) or dt in ("사업의종류", "종류", "사업의")


def _find_region(res, H):
    """'사업의 종류' 라인과 그 아래 종료 앵커로 y범위 + 라벨 오른쪽 끝 x 결정."""
    start = None
    for b, t, c in res:
        if _is_anchor(t) and c > 0.2:
            if start is None or _cy(b) < _cy(start[0]):
                start = (b, t, c)
    if start is None:
        return None
    y0 = _cy(start[0])
    label_right = max(p[0] for p in start[0])  # 앵커 오른쪽 끝
    end_y = None
    for b, t, c in res:
        dt = _despace(t)
        if _cy(b) > y0 + 20 and any(k in dt for k in ("발급사유", "교부사유", "발급", "교부", "전자세금", "공동사업")):
            if end_y is None or _cy(b) < end_y:
                end_y = _cy(b)
    y_bot = (end_y - 10) if end_y else min(H, y0 + H * 0.16)
    return y0 - 20, y_bot, label_right


def _column_split(items):
    """region items([(x,y,text)]) → 종목 칼럼 시작 x경계.

    업태 값들은 왼쪽, 종목 값들은 오른쪽에 모여 있고 그 사이에 큰 빈 구간이 있다.
    x중심들을 정렬해 '가장 큰 간격'에서 나눈다. 단 그 간격이 충분히 커야 함.
    """
    xs = sorted(it[0] for it in items)
    if len(xs) < 2:
        return None
    # 양쪽에 박스가 2개 이상 있는 간격 중 가장 큰 것에서 분리 (바깥 잡음 무시)
    best = None
    for i in range(len(xs) - 1):
        left_n, right_n = i + 1, len(xs) - i - 1
        if left_n >= 1 and right_n >= 1:
            g = xs[i + 1] - xs[i]
            if best is None or g > best[0]:
                best = (g, (xs[i] + xs[i + 1]) / 2)
    if best is None or best[0] < 120:
        return None
    return best[1]


def _clean_val(t):
    """값 앞뒤 라벨/괄호 잡음 제거: '[레 제조업'→'제조업', '종 류 서비스업'→'서비스업'."""
    t = re.sub(r"^[\[\](){}·:'\"\s]+", "", t)
    t = re.sub(r"^(종\s*류|업\s*태|종\s*목|사\s*업\s*의\s*종\s*류)\s*", "", t)
    t = re.sub(r"^\[?(레|총혹|총목|업태|종목)\]?\s*", "", t)
    return t.strip(" '\"[]()")


def _cluster_rows(col_items, gap=34):
    """같은 칼럼 박스들을 y로 묶어 줄(행) 단위로. 접힌 줄은 이어붙임.
    각 행 = (y_center, 텍스트). 행 내부는 (y, x) 순서로 이어붙인다(윗줄 먼저)."""
    col_items = sorted(col_items, key=lambda it: it[1])
    rows, cur = [], []
    for x, y, t in col_items:
        if cur and y - cur[-1][1] > gap:
            rows.append(cur)
            cur = []
        cur.append((x, y, t))
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        r.sort(key=lambda it: (round(it[1] / 16), it[0]))  # 윗줄 먼저, 그 안에서 왼→오
        words = []
        for _, _, t in r:
            for w in _clean_val(t).split():
                words.append(w)
        # 근접 중복 단어 제거: "도매 및 도매 및 소매업" → "도매 및 소매업"
        # (1글자 조사 '및' 등은 정상적으로 반복되므로 제외)
        dedup = []
        for w in words:
            if dedup and w == dedup[-1]:
                continue  # 바로 앞과 같은 단어 (길이 무관)
            if len(w.strip(",.·")) >= 2 and w in dedup[-4:]:
                continue  # 근접 반복된 2글자 이상 단어
            dedup.append(w)
        txt = _clean_val(" ".join(dedup))
        if not txt or not _has_hangul(txt):
            continue
        yc = min(y for _, y, _ in r)
        out.append((yc, txt))
    return out


def _group(up_rows, jo_rows):
    up_rows = sorted(up_rows)
    jo_rows = sorted(jo_rows)
    if not up_rows:
        return [{"업태": "", "종목": [t for _, t in jo_rows]}]
    bnds = [y for y, _ in up_rows] + [1e9]
    groups = [{"업태": t, "종목": []} for _, t in up_rows]
    for y, t in jo_rows:
        gi = len(up_rows) - 1
        for i in range(len(up_rows)):
            lo = (bnds[i] + bnds[i - 1]) / 2 if i > 0 else -1e9
            hi = (bnds[i] + bnds[i + 1]) / 2 if i + 1 < len(bnds) else 1e9
            if lo <= y < hi:
                gi = i
                break
        groups[gi]["종목"].append(t)
    return groups


_LABEL = {"업태", "종목", "종목1", "업태1"}


def _merge_boxes(*box_lists):
    """여러 OCR 결과(normal/enhanced) 병합. 위치가 겹치면 conf 높은 것만 남긴다."""
    merged = []  # [x, y, t, c]
    for res in box_lists:
        for b, t, c in res:
            x, y = _cx(b), _cy(b)
            hit = None
            for i, (mx, my, mt, mc) in enumerate(merged):
                if abs(x - mx) < 60 and abs(y - my) < 22:
                    hit = i
                    break
            if hit is None:
                merged.append([x, y, t, c])
            elif c > merged[hit][3]:
                merged[hit] = [x, y, t, c]
    return merged


_JONG_LABEL_RE = re.compile(r"^[\[\(]?[종총][목록옥혹기]")


def _is_jong_label(t):
    dt = _despace(t)
    return bool(_JONG_LABEL_RE.match(dt)) and len(dt) <= 4


def _has_hangul(s):
    return bool(re.search(r"[가-힣]", s))


def _norm(s):
    return re.sub(r"[\s,.·]", "", s)


def _best_match(text, candidates, threshold=0.55):
    nt = _norm(text)
    if not nt:
        return None
    best, br = None, 0.0
    for c in candidates:
        r = difflib.SequenceMatcher(None, nt, _norm(c)).ratio()
        # 한쪽이 다른쪽에 포함되면 가산 (접힘/일부누락 대응)
        if _norm(c) and (_norm(c) in nt or nt in _norm(c)):
            r = max(r, 0.8)
        if r > br:
            best, br = c, r
    return best if br >= threshold else None


def _qwen_texts(im, qwen):
    """Qwen으로 업태/종목 텍스트만 정확히 읽어 (업태리스트, 종목리스트) 반환."""
    from backend.assistant.biz_cert_ocr import ask_image, parse_json

    model, processor = qwen
    raw = ask_image(model, processor, im, _QWEN_TEXT_PROMPT)
    p = parse_json(raw) or {}
    up_raw = p.get("업태목록") or p.get("업태") or []
    jo_raw = p.get("종목목록") or p.get("종목") or []
    up = [str(x).strip() for x in up_raw if str(x).strip() and _despace(str(x)) not in _LABEL]
    jo = [str(x).strip() for x in jo_raw if str(x).strip() and _despace(str(x)) not in _LABEL]
    return up, jo


def _refine_val(easy_text, pool):
    """EasyOCR 값을 Qwen이 읽은 텍스트로 교체 — 단, 짧아지지 않을 때만 (누락 방지)."""
    m = _best_match(easy_text, pool, threshold=0.62)
    if not m:
        return easy_text
    if len(_norm(m)) < len(_norm(easy_text)) * 0.9:
        return easy_text  # Qwen이 잘라먹은 경우 → EasyOCR 유지
    return m


def _merge_to_count(items, n):
    """items를 n개로 줄임: 인접 항목을 이어붙여 개수 맞춤 (Qwen이 한 줄을 쪼갠 경우)."""
    if len(items) <= n or n <= 0:
        return items
    items = list(items)
    while len(items) > n:
        # 가장 짧은 항목을 앞 항목에 병합
        i = min(range(1, len(items)), key=lambda k: len(_norm(items[k])))
        items[i - 1] = (items[i - 1] + ", " + items[i]).strip(", ")
        items.pop(i)
    return items


def _refine(groups, im, qwen, debug=False):
    up_list, jo_list = _qwen_texts(im, qwen)
    pool = [x for x in (up_list + jo_list) if x]  # Qwen이 칼럼을 헷갈려도 되도록 통합 풀
    if debug:
        print(f"  [debug] Qwen 업태: {up_list}")
        print(f"  [debug] Qwen 종목: {jo_list}")

    # 텍스트 보정만 (짧아지지 않는 선에서 Qwen 텍스트로 교체). 누락 채우기는 하지 않음
    # — Qwen 목록이 불완전/분할되는 경우가 많아 오히려 정렬을 깨뜨림.
    for g in groups:
        g["업태"] = _refine_val(g["업태"], pool)
        g["종목"] = [_refine_val(j, pool) for j in g["종목"]]
    return groups


def extract_categories(path_or_im, enhance="auto", qwen=None, debug=False):
    im = _prep(path_or_im)
    H = im.height
    res = _ocr(im)
    res_e = _ocr(_enhance(im)) if enhance in ("auto", True) else []

    region = _find_region(res, H) or (_find_region(res_e, H) if res_e else None)
    if region is None:
        if debug:
            print("  [debug] '사업의 종류' 영역 못 찾음")
        return []

    y0, y1, label_x = region
    boxes = _merge_boxes(res, res_e)
    in_region = [(x, y, t, c) for x, y, t, c in boxes
                 if y0 <= y <= y1 and x > label_x - 40 and c > 0.12]

    # '종목' 라벨 박스 → 칼럼 분리 x 기준
    jong_label_x = None
    for x, y, t, c in in_region:
        if _is_jong_label(t):
            jong_label_x = x if jong_label_x is None else min(jong_label_x, x)

    items = [
        (x, y, t.strip())
        for x, y, t, c in in_region
        if not _is_anchor(t) and not _is_jong_label(t)
        and _despace(t) not in _LABEL
        and _has_hangul(_clean_val(t)) and len(_clean_val(t)) >= 2
    ]
    if debug:
        print(f"  [debug] 영역 y={y0:.0f}~{y1:.0f}, 종목라벨x={jong_label_x}, 박스 {len(items)}개")
        for x, y, t in sorted(items, key=lambda i: i[1]):
            print(f"    y={y:6.0f} x={x:6.0f}  {t!r}")

    split = jong_label_x - 20 if jong_label_x else _column_split(items)
    if split is None:
        return []
    up = [(x, y, t) for x, y, t in items if x < split]
    jo = [(x, y, t) for x, y, t in items if x >= split]

    up_rows = _cluster_rows(up)
    jo_rows = _cluster_rows(jo)
    if debug:
        print(f"  [debug] up_rows={up_rows}")
        print(f"  [debug] jo_rows={jo_rows}")

    # 더 완전한(행 많은) 칼럼을 기준 행으로, 다른 칼럼 값은 가장 가까운 기준행에 배정
    if len(jo_rows) >= len(up_rows) and jo_rows:
        anchors = [y for y, _ in jo_rows]
        groups = [{"업태": "", "종목": [t]} for _, t in jo_rows]
        for y, t in up_rows:
            i = min(range(len(anchors)), key=lambda k: abs(anchors[k] - y))
            groups[i]["업태"] = (groups[i]["업태"] + " " + t).strip()
    else:
        groups = _group(up_rows, jo_rows)

    if qwen is not None:
        try:
            groups = _refine(groups, im, qwen, debug)
        except Exception as e:
            if debug:
                print(f"  [debug] Qwen 보정 실패: {e}")
    return groups


def is_low_confidence(groups):
    """업태·종목 추출 결과가 신뢰하기 어려운지 판정 (프론트 '확인해주세요' 플래그용).

    구조가 온전하면(모든 그룹에 업태와 종목이 채워짐) 통과. 글자 오독은 여기서 판정하지
    않는다(다운스트림 KSIC 정규화가 흡수). 비어 있는 칸이 있으면 인식 실패로 본다.
    """
    if not groups:
        return True, "업태·종목을 찾지 못함"
    for g in groups:
        if not g.get("업태", "").strip():
            return True, "일부 업태를 읽지 못함"
        if not any(x.strip() for x in g.get("종목", [])):
            return True, "일부 종목을 읽지 못함"
    return False, ""


if __name__ == "__main__":
    import sys

    for p in sys.argv[1:]:
        print(f"=== {p} ===")
        gs = extract_categories(p, debug=True)
        for g in gs:
            print(f"  {g['업태']}  →  {', '.join(g['종목'])}")
        low, reason = is_low_confidence(gs)
        print(f"  needs_review={low}  {reason}")
        print()
