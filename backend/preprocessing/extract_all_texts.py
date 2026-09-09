# extract_all_texts.py (통합본 — file_extract.py 안 불러오고 다 여기 안에 있음)
#
# bizinfo.csv(1,589건) 전체를 돌면서 printFlpthNm으로 원문을 다운로드·추출한다.
# PDF/HWP/HWPX/스캔PDF(OCR) 처리 함수들을 file_extract.py에서 그대로 가져와
# 이 파일 안에 통째로 넣었다 — 다른 파일 안 불러와도 이 파일 하나로 완결됨.
#
# 재시도 로직: "실패"로 기록된 것만 다음 실행에서 다시 시도한다
# (성공한 것 중복 처리 안 함, 실패한 것 계속 재시도 가능)

import csv
import gc
import io
import logging
import os
import re
import sys
import tempfile
import time
import zipfile
import argparse

import requests
import pdfplumber

# pyhwp(hwp5)가 일부 HWP 파일의 밑줄 스타일 값이 자기가 아는 범위 밖이면
# logger.warning()으로 파일 하나당 수백~수천 줄씩 찍는 경우가 실측 확인됨
# (관리자 화면 실행 로그를 도배해서 정작 우리 쪽 진행 요약을 못 보게 만듦).
# 추출 결과 자체엔 영향 없는 경고라 조용히 시킨다.
logging.getLogger("hwp5").setLevel(logging.ERROR)

# [2026-09 추가] 파이썬 csv 모듈의 기본 필드 크기 제한(131,072자)을 없앰.
# 원문이 긴 공고(19만자 넘는 것도 실측 확인됨)를 다시 읽을 때
# "field larger than field limit" 에러가 나는 걸 막기 위함.
# sys.maxsize를 그대로 쓰면 Windows에서 OverflowError가 나는 경우가 있어
# 충분히 큰 고정값(1000만자)으로 대신 지정.
csv.field_size_limit(10_000_000)

BASE = os.path.dirname(os.path.abspath(__file__))

# [2026-09-05 주석처리] data/raw/bizinfo.csv를 미리 준비해서 배치로 도는 방식
# 대신, API에서 받은 데이터를 바로 pipeline.process_notice()에 넘겨 처리하는
# 방식을 쓰기로 해서 이 CSV 경로들(과 이걸 쓰는 main() 배치 실행부)은 당분간
# 안 쓴다. get_notice_full_text() 등 추출 함수 자체는 pipeline.py가 그대로
# 가져다 쓰므로 그대로 둔다.
# RAW_CSV_DEFAULT = os.path.join(BASE, "data", "raw", "bizinfo.csv")
# OUT_CSV_DEFAULT = os.path.join(BASE, "data", "outputs", "full_raw_texts_1589.csv")
#
# # main()에서 --input/--output 인자로 실제 값이 채워짐 (기본값은 위 상수)
# RAW_CSV = RAW_CSV_DEFAULT
# OUT_CSV = OUT_CSV_DEFAULT

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# OCR 모델은 무거우므로 최초 1회만 로딩해서 재사용
_ocr_reader = None
_ocr_disabled = False  # --skip-ocr 옵션으로 켜짐
_cuda_dlls_preloaded = False

# [2026-09-09] 파일당 처리 단계(다운로드/PDF/HWP/HWPX/OCR)별 진단 로그가
# 통합 반영 실행 로그(관리자 화면)를 너무 도배해서, 기본은 끄고 필요할 때만
# (EXTRACT_DEBUG=1) 켜도록 함. 건별 성공/실패 요약은 sync_bizinfo_announcements.py
# 쪽에서 별도로 항상 찍는다.
_DEBUG = os.environ.get("EXTRACT_DEBUG") == "1"


def _debug_print(msg):
    if _DEBUG:
        print(msg)


def _preload_cuda_dlls():
    """[2026-09 추가] Windows에서 paddlepaddle-gpu가 cublasLt64_13.dll을
    "Could not locate cublasLt64_13.dll" 에러(파이썬 예외가 아니라 프로세스가
    통째로 죽는 크래시)로 못 찾는 문제 우회.

    실측 확인한 원인: pip로 설치되는 nvidia-cublas/nvidia-cudnn 패키지의 DLL은
    site-packages\\nvidia\\... 하위에 있는데, 이 경로가 프로세스의 DLL 검색
    경로에 없음. os.add_dll_directory()로 그 경로를 추가해도 paddle이 이름만
    으로 로드를 시도할 때는 여전히 실패했음(재현 확인됨) — 반면 ctypes로
    "절대경로"를 줘서 한번 프로세스에 로드해두면, 그 다음부터는 이름만으로
    찾는 호출도 이미 로드된 모듈을 그대로 찾아써서 성공함(재현 확인됨).
    그래서 paddle을 import하기 전에 nvidia 패키지 밑의 dll을 전부 미리 로드.
    """
    global _cuda_dlls_preloaded
    if _cuda_dlls_preloaded or os.name != "nt":
        return
    _cuda_dlls_preloaded = True

    try:
        import ctypes
        import importlib.util

        spec = importlib.util.find_spec("nvidia")
        if not spec or not spec.submodule_search_locations:
            return
        for base in spec.submodule_search_locations:
            for root, _dirs, files in os.walk(base):
                for f in files:
                    if f.lower().endswith(".dll"):
                        try:
                            ctypes.WinDLL(os.path.join(root, f))
                        except OSError:
                            pass  # 이 DLL이 없어도 다른 게 될 수 있으니 계속 진행
    except Exception:
        pass  # GPU용 DLL 프리로드는 어디까지나 보조 수단, 실패해도 계속 진행


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        _preload_cuda_dlls()
        from paddleocr import PaddleOCR
        # [2026-09 수정] use_gpu=True를 강제로 넘겼다가 최신 PaddleOCR(3.x)에서
        # 이 옵션 자체가 없어지거나 오류를 일으키는 사례가 실제로 다수 보고됨
        # (GitHub 이슈: use_gpu 관련 TypeError, set_optimization_level 누락 등).
        # 옵션을 아예 안 주면 라이브러리가 자동으로 GPU 있으면 GPU, 없으면 CPU를
        # 씀(공식 문서 기준) — 이게 지금 버전들과 제일 안전하게 맞는 방식.
        _ocr_reader = PaddleOCR(lang="korean")
        _debug_print("  [OCR] 로딩 완료(GPU 있으면 자동으로 사용)")
    return _ocr_reader


def detect_file_type(content):
    """파일 내용(bytes)의 매직바이트로 실제 형식 판별"""
    if content[:4] == b"%PDF":
        return "pdf"
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "hwp"
    if content[:2] == b"PK":
        return "hwpx_or_zip"
    # [2026-09-03 추가] 실패 71건을 재검수한 결과 87.3%(62건)가 PDF/HWP/HWPX가
    # 아니라 첨부파일 자체가 포스터·전단지 이미지(PNG/JPG)였음이 확인됨.
    # 지금까지 이런 파일은 형식 검사에서 아예 안 걸려서 unknown_format으로
    # 버려지고 있었음 — OCR 리더는 이미 있으니 이미지도 바로 넣어주면 됨.
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image"
    if content[:3] == b"\xff\xd8\xff":
        return "image"
    return "unknown"


def extract_text_from_pdf(content):
    """텍스트 기반 PDF에서 텍스트 추출. 실패(스캔본 등)하면 None"""
    try:
        texts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    texts.append(page_text)
        result = "\n".join(texts)
        return result if result.strip() else None
    except Exception as e:
        _debug_print(f"    [PDF진단] pdfplumber 실패: {type(e).__name__}: {e}")
        return None


def _hwp5_prvtext_fallback(tmp_path):
    """[2026-09-03 추가] 정식 본문 추출(XSLT 변환)이 통째로 실패하는 HWP가
    실측 확인됨(문서 안에 XML 1.0이 허용 안 하는 제어문자가 섞인 경우) — 이런
    파일도 OLE 안의 "PrvText"(미리보기 텍스트) 스트림은 별도 raw 문자열이라
    안전하게 읽힌다. 완전한 본문은 아니지만(미리보기 분량) 아예 못 뽑는 것보단
    낫다. PrvText 스트림 자체가 없는 파일(구조가 더 단순한 문서)도 있음."""
    import olefile

    try:
        with olefile.OleFileIO(tmp_path) as ole:
            if not ole.exists("PrvText"):
                return None
            raw = ole.openstream("PrvText").read()
        text = raw.decode("utf-16le", errors="ignore")
        return text if text.strip() else None
    except Exception as e:
        _debug_print(f"    [HWP진단] PrvText 폴백도 실패: {type(e).__name__}: {e}")
        return None


def extract_text_from_hwp(content):
    """구버전 HWP(OLE)에서 텍스트 추출. hwp5txt CLI 대신 pyhwp 파이썬 API를
    직접 호출한다.

    [2026-09-03 변경] 실패 71건을 재검수하다가, 겉보기엔 멀쩡한 HWP 파일 3건이
    전부 같은 이유로 hwp5txt에서 죽는 걸 실측 확인함:
    AttributeError: 'OleStream' object has no attribute 'propertySetStream'
    — 본문(BodyText)이 아니라 "요약정보"(제목/작성자 등 메타데이터) 스트림을
    파싱하다 pyhwp 자체 버그로 죽는 것. 정상 파일로 직접 대조해보니 이 요약
    정보를 건너뛰어도 본문 추출 결과가 100% 동일해서(bytewise identical),
    요약정보 파싱은 아예 하지 않도록 우회한다 — 본문 추출엔 필요 없는
    단계였음.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        from hwp5.xmlmodel import Hwp5File
        from hwp5.hwp5txt import TextTransform

        hwp5file = Hwp5File(tmp_path)
        try:
            hwp5file.summaryinfo.events = lambda **kwargs: iter([])  # 위 설명대로 우회
            out = io.BytesIO()
            TextTransform().transform_hwp5_to_text(hwp5file, out)
            text = out.getvalue().decode("utf-8", errors="ignore")
        finally:
            hwp5file.close()

        if text and text.strip():
            return text, "full"
        raise ValueError("본문 추출 결과가 비어있음")
    except Exception as e:
        # [2026-09-03] 요약정보 우회로도 못 넘는 경우(예: 본문 안에 XML로
        # 직렬화 불가능한 제어문자가 섞인 경우)가 실측 확인됨 — 이때는
        # PrvText(미리보기) 스트림으로 최소한의 텍스트라도 건진다.
        _debug_print(f"    [HWP진단] pyhwp 본문 추출 실패({type(e).__name__}: {e}) -> PrvText 폴백 시도")
        fallback = _hwp5_prvtext_fallback(tmp_path) if tmp_path else None
        return (fallback, "preview") if fallback else (None, None)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def extract_text_from_hwpx(content):
    """HWPX(zip+xml) 또는 docx(zip+xml)에서 순수 파이썬으로 텍스트 추출.

    [2026-09-03 확장] 실패 71건 재검수 중 1건이 HWPX가 아니라 docx(zip 안에
    word/document.xml)였음이 확인됨 — 같은 "PK 매직바이트"(hwpx_or_zip) 분기를
    타지만 내부 구조가 달라 기존 hwpx 파서로는 못 잡았음. zip 안의 실제 파일
    구성을 보고 hwpx/docx 중 어느 쪽인지 판별해서 각각의 태그로 추출한다.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            names = z.namelist()
            section_files = sorted([
                n for n in names if "section" in n.lower() and n.endswith(".xml")
            ])
            if section_files:
                texts = []
                for section_file in section_files:
                    xml_content = z.read(section_file).decode("utf-8", errors="ignore")
                    matches = re.findall(r"<hp:t[^>]*>(.*?)</hp:t>", xml_content, re.DOTALL)
                    for m in matches:
                        clean = re.sub(r"<[^>]+>", "", m)
                        if clean.strip():
                            texts.append(clean.strip())
                result = "\n".join(texts)
                return (result, "hwpx") if result.strip() else (None, None)

            if "word/document.xml" in names:
                xml_content = z.read("word/document.xml").decode("utf-8", errors="ignore")
                paragraphs = re.findall(r"<w:p[ >].*?</w:p>", xml_content, re.DOTALL)
                texts = []
                for p in paragraphs:
                    runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.DOTALL)
                    line = "".join(re.sub(r"<[^>]+>", "", r) for r in runs)
                    if line.strip():
                        texts.append(line.strip())
                result = "\n".join(texts)
                return (result, "docx") if result.strip() else (None, None)

        return None, None
    except Exception as e:
        _debug_print(f"    [HWPX진단] zip/xml 파싱 실패: {type(e).__name__}: {e}")
        return None, None


def _resize_if_too_big(img_array, max_side=4000, label=""):
    """[안전장치] 가로/세로 4000px 초과 이미지는 PaddleOCR 내부(C++ 레벨)에서
    예외 없이 그냥 죽는 경우가 실측 확인됨(try/except로도 못 잡힘). 미리
    축소해서 크래시 방지. extract_text_from_scanned_pdf/이미지 추출 공용."""
    import numpy as np
    from PIL import Image as PILImage

    h, w = img_array.shape[:2]
    if max(h, w) <= max_side:
        return img_array
    scale = max_side / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    _debug_print(f"    [OCR진단] {label}너무 커서 리사이즈: ({w},{h}) -> ({new_w},{new_h})")
    return np.array(PILImage.fromarray(img_array).resize((new_w, new_h)))


def extract_text_from_image(content):
    """[2026-09-03 추가] 첨부파일 자체가 PNG/JPG인 경우 — PDF 렌더링 단계 없이
    이미지를 바로 OCR에 넣는다. 스캔 PDF 처리(extract_text_from_scanned_pdf)와
    같은 PaddleOCR 리더·리사이즈 안전장치를 그대로 재사용."""
    if _ocr_disabled:
        return None
    try:
        import numpy as np
        from PIL import Image as PILImage

        img = PILImage.open(io.BytesIO(content)).convert("RGB")
        img_array = np.array(img)
        _debug_print(f"    [OCR진단] 이미지 크기: {img_array.shape}")
        img_array = _resize_if_too_big(img_array)

        reader = _get_ocr_reader()
        result = reader.predict(img_array)
        texts = []
        for res in result:
            texts.extend(res["rec_texts"])
        del result
        gc.collect()

        result_text = "\n".join(texts)
        return result_text if result_text.strip() else None
    except Exception as e:
        _debug_print(f"    [OCR진단] 이미지 OCR 처리 실패: {type(e).__name__}: {e}")
        return None


def extract_text_from_scanned_pdf(content):
    """텍스트 레이어 없는 스캔 PDF를 OCR로 처리. --skip-ocr면 즉시 포기.

    [2026-09 변경] 렌더링을 pdf2image(Poppler 서브프로세스 호출)에서
    PyMuPDF로 교체함. 실측 확인 결과 Poppler 26.02.0이 특정 스캔 PDF
    (JPEG 이미지 + 오브젝트 스트림 압축 조합)에서 pdfinfo/pdftoppm 둘 다
    세그폴트를 일으켰음 — 파일 자체는 pdfplumber로 정상 열리는 멀쩡한
    파일이었고, PyMuPDF로는 동일 파일이 문제없이 렌더링됨. 외부 프로세스
    호출이 없어져서 timeout/poppler_path 관리도 불필요해짐.
    """
    if _ocr_disabled:
        return None
    try:
        import pymupdf
        import numpy as np
        from PIL import Image as PILImage

        doc = pymupdf.open(stream=content, filetype="pdf")
        _debug_print(f"    [OCR진단] 페이지 수: {doc.page_count}")
        reader = _get_ocr_reader()

        texts = []
        for page_num in range(doc.page_count):
            pix = doc[page_num].get_pixmap(dpi=150)
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:  # 알파 채널 있으면 제거
                img_array = img_array[:, :, :3]

            # [안전장치 유지] 너무 큰 이미지(가로/세로 4000px 초과)는 리사이즈
            # 안 하면 PaddleOCR 내부(C++ 레벨)에서 예외 없이 그냥 죽는 경우가
            # 실측 확인됨(try/except로도 못 잡힘). 미리 축소해서 크래시 방지.
            h, w = img_array.shape[:2]
            max_side = 4000
            if max(h, w) > max_side:
                scale = max_side / max(h, w)
                new_w, new_h = int(w * scale), int(h * scale)
                img_array = np.array(PILImage.fromarray(img_array).resize((new_w, new_h)))
                _debug_print(f"    [OCR진단] {page_num + 1}페이지 너무 커서 리사이즈: ({w},{h}) -> ({new_w},{new_h})")

            _debug_print(f"    [OCR진단] {page_num + 1}페이지 크기: {img_array.shape}")
            result = reader.predict(img_array)
            for res in result:
                texts.extend(res["rec_texts"])
            del result
            gc.collect()

        doc.close()

        result_text = "\n".join(texts)
        return result_text if result_text.strip() else None
    except Exception as e:
        _debug_print(f"    [OCR진단] OCR 처리 실패: {type(e).__name__}: {e}")
        return None


def get_notice_full_text(print_flpth_url):
    """printFlpthNm URL 하나를 받아 본문 텍스트를 추출.
    반환값: (텍스트 또는 None, 상태 메시지)"""
    if not print_flpth_url or not print_flpth_url.strip():
        return None, "no_url"

    # [2026-09 추가] 다운로드가 중간에 끊겨 반쪽짜리 파일이 되는 경우가
    # 실측(같은 파일이 계속 "Unexpected EOF"로 실패)으로 확인되어 재시도 추가.
    content = None
    for attempt in range(3):
        try:
            response = requests.get(print_flpth_url, headers=HEADERS, timeout=20)
            if response.status_code != 200:
                if attempt < 2:
                    time.sleep(1.5)
                    continue
                return None, "download_failed"
            content = response.content

            # Content-Length 헤더가 있으면, 실제로 받은 바이트 수랑 비교해서
            # 중간에 끊긴 다운로드인지 확인. 불일치하면 재시도.
            expected_len = response.headers.get("Content-Length")
            if expected_len and int(expected_len) != len(content):
                _debug_print(f"    [다운로드진단] 크기 불일치(예상 {expected_len} / 실제 {len(content)}) "
                             f"-> 재시도({attempt + 1}/3)")
                if attempt < 2:
                    time.sleep(1.5)
                    continue
            break
        except Exception:
            if attempt < 2:
                time.sleep(1.5)
                continue
            return None, "download_failed"

    if content is None:
        return None, "download_failed"

    file_type = detect_file_type(content)

    if file_type == "pdf":
        text = extract_text_from_pdf(content)
        if text:
            return text, "success_pdf"
        text = extract_text_from_scanned_pdf(content)
        return (text, "success_ocr") if text else (None, "extract_failed")

    if file_type == "hwp":
        text, kind = extract_text_from_hwp(content)
        if not text:
            return None, "extract_failed"
        return (text, "success_hwp") if kind == "full" else (text, "success_hwp_preview")

    if file_type == "hwpx_or_zip":
        text, kind = extract_text_from_hwpx(content)
        if not text:
            return None, "extract_failed"
        return (text, "success_hwpx") if kind == "hwpx" else (text, "success_docx")

    if file_type == "image":
        text = extract_text_from_image(content)
        return (text, "success_ocr_image") if text else (None, "extract_failed")

    return None, "unknown_format"


# ============================================================
# 여기부터 "1,589건 전체 돌리기" 배치 실행 로직
#
# [2026-09-05 주석처리] data/raw/bizinfo.csv를 미리 준비해두고 그걸 읽어서
# 첨부파일을 순회 다운로드하던 배치 실행부. API로 받은 데이터를 CSV로 캐싱하는
# 단계 없이 바로 pipeline.process_notice()에 넘겨서 처리하는 방식으로 대체
# 하기로 해서 이 배치 진입점(load_csv/load_already_success/write_all/main)은
# 당분간 쓰지 않는다. get_notice_full_text() 등 위쪽 추출 함수들은 그대로
# 쓰이므로(pipeline.py가 직접 import) 안 건드림. 필요해지면 주석만 풀면 됨.
# ============================================================

# def load_csv(path):
#     with open(path, encoding="utf-8-sig") as f:
#         return list(csv.DictReader(f))
#
#
# def load_already_success():
#     """이미 '성공'한 공고ID만 건너뛰기 위함(실패한 건 재시도 대상으로 남김)."""
#     if not os.path.exists(OUT_CSV):
#         return {}
#     with open(OUT_CSV, encoding="utf-8-sig") as f:
#         rows = list(csv.DictReader(f))
#     return {r["공고ID"]: r for r in rows if r.get("원문", "").strip()}
#
#
# def write_all(rows, fieldnames):
#     os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
#     with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
#         writer = csv.DictWriter(f, fieldnames=fieldnames)
#         writer.writeheader()
#         writer.writerows(rows)
#
#
# def main():
#     global _ocr_disabled, RAW_CSV, OUT_CSV
#
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--skip-ocr", action="store_true",
#                          help="스캔본 PDF(OCR 필요)는 건너뛰고 나머지만 빠르게 먼저 처리")
#     parser.add_argument("--input", default=None,
#                          help="입력 CSV 경로(기본: data/raw/bizinfo.csv). "
#                               "예: --input ../data/raw/bizinfo_sample.csv (100건 테스트용)")
#     parser.add_argument("--output", default=None,
#                          help="출력 CSV 경로(기본: data/outputs/full_raw_texts_1589.csv). "
#                               "--input 바꾸면 이것도 같이 바꿔서 기존 결과 안 덮어쓰게 할 것")
#     args = parser.parse_args()
#     _ocr_disabled = args.skip_ocr
#
#     if args.input:
#         RAW_CSV = os.path.abspath(os.path.join(BASE, args.input)) if not os.path.isabs(args.input) else args.input
#     if args.output:
#         OUT_CSV = os.path.abspath(os.path.join(BASE, args.output)) if not os.path.isabs(args.output) else args.output
#
#     print(f"[설정] 입력 파일: {RAW_CSV}")
#     print(f"[설정] 출력 파일: {OUT_CSV}\n")
#
#     # 시작하자마자 PyMuPDF를 실제로 불러올 수 있는지 먼저 확인.
#     try:
#         import pymupdf
#         print(f"[시작확인] PyMuPDF 찾음: v{pymupdf.__version__}")
#     except ImportError:
#         print("[시작확인] *** 경고: PyMuPDF를 못 찾았습니다! OCR이 필요한 스캔본은 전부 실패합니다."
#               " (pip install pymupdf) ***")
#     print()
#
#     if _ocr_disabled:
#         print("*** --skip-ocr 모드: 스캔본은 건너뛰고 나머지만 먼저 처리합니다 ***\n")
#
#     rows = load_csv(RAW_CSV)
#     already_success = load_already_success()
#     print(f"총 {len(rows)}건 중 이미 성공한 것: {len(already_success)}건 "
#           f"(나머지 {len(rows) - len(already_success)}건을 이번에 시도합니다)")
#
#     fieldnames = ["번호", "공고ID", "공고명", "원문", "추출상태"]
#     success_cnt = 0
#     fail_cnt = 0
#     final_rows = []
#
#     for i, row in enumerate(rows, start=1):
#         notice_id = row.get("pblancId", "")
#
#         if notice_id in already_success:
#             final_rows.append(already_success[notice_id])
#             success_cnt += 1
#             continue
#
#         url = row.get("printFlpthNm", "")
#         t0 = time.time()
#         text, status = get_notice_full_text(url)
#         elapsed = time.time() - t0
#
#         new_row = {
#             "번호": i,
#             "공고ID": notice_id,
#             "공고명": row.get("pblancNm", ""),
#             "원문": text or "",
#             "추출상태": status,
#         }
#         final_rows.append(new_row)
#
#         if text:
#             success_cnt += 1
#         else:
#             fail_cnt += 1
#
#         mark = "OK" if text else "FAIL"
#         slow = " <- 느림" if elapsed > 5 else ""
#         print(f"  [{i}/{len(rows)}] {mark} {status} ({elapsed:.1f}초){slow} | 누적 성공{success_cnt}/실패{fail_cnt}")
#
#         time.sleep(0.3)
#
#         if i % 20 == 0:
#             write_all(final_rows, fieldnames)
#
#     write_all(final_rows, fieldnames)
#
#     print(f"\n완료: {OUT_CSV}")
#     print(f"이번 실행 기준 - 전체 {len(rows)}건 중 성공 {success_cnt}건 / 실패 {fail_cnt}건")
#     if _ocr_disabled and fail_cnt > 0:
#         print(f"(--skip-ocr 모드였음 — 실패 {fail_cnt}건은 스캔본일 가능성이 높음. "
#               f"'python extract_all_texts.py'를 옵션 없이 다시 돌리면 이 실패분만 OCR로 재시도됩니다)")
#
#
# if __name__ == "__main__":
#     main()
