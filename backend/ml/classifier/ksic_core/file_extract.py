# ============================================================
# ksic_core/file_extract.py
#
# 목적
# ------------------------------------------------------------
# printFlpthNm(본문출력경로명) URL 하나를 받아서
# 1) 다운로드
# 2) 매직바이트로 실제 파일 형식 판별 (파일명 메타데이터는 못 믿음)
# 3) 형식에 맞는 방법으로 텍스트 추출
#    - PDF: pdfplumber
#    - HWP(구버전 OLE): hwp5txt (커맨드라인 도구, subprocess로 호출)
#    - HWPX(zip 기반): 아직 지원 안 함 -> None 반환 (호출부에서 폴백 처리)
#
# 실패하면 예외를 던지지 않고 None을 반환한다.
# (한 건 실패했다고 전체 파이프라인이 멈추면 안 되니까)
# ============================================================
# ============================================================
# ksic_core/file_extract.py
#
# printFlpthNm(본문출력경로명) URL 하나를 받아서
# 실제 형식(PDF/HWP/HWPX/스캔PDF)을 판별하고
# 각각에 맞는 방법으로 텍스트를 추출한다.
#
# 우선순위: 텍스트 기반 PDF > HWP > HWPX > 스캔 PDF(OCR)
# 전부 실패하면 None을 반환하고, 호출부에서 요약문으로 폴백한다.
# ============================================================

import io
import os
import re
import subprocess
import tempfile
import zipfile

import requests
import pdfplumber


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# OCR 모델은 무거우므로 최초 1회만 로딩해서 재사용
_ocr_reader = None
_cuda_dlls_preloaded = False


def _preload_cuda_dlls():
    """pip로 설치되는 nvidia-cublas/nvidia-cudnn의 DLL은
    site-packages\\nvidia\\... 밑에 있는데 이 경로가 프로세스의 DLL 검색
    경로에 없어서, paddle이 이름만으로 로드를 시도하면 실패한다(WinError 127).
    ctypes로 절대경로를 줘서 한 번 프로세스에 미리 로드해두면 그 다음부터는
    이름만으로 찾는 호출도 이미 로드된 모듈을 그대로 찾아써서 성공한다."""
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
        dll_paths = []
        for base in spec.submodule_search_locations:
            for root, _dirs, files in os.walk(base):
                for f in files:
                    if f.lower().endswith(".dll"):
                        dll_paths.append(os.path.join(root, f))

        # 일부 DLL은 다른 DLL이 먼저 로드돼 있어야 로드된다(예: cudnn_cnn64_9.dll는
        # cudnn_ops64_9.dll에 의존). 의존순서를 미리 알 수 없으므로, 더 이상
        # 진전이 없을 때까지 실패한 것만 재시도한다.
        remaining = dll_paths
        while remaining:
            still_failed = []
            for path in remaining:
                try:
                    ctypes.WinDLL(path)
                except OSError:
                    still_failed.append(path)
            if len(still_failed) == len(remaining):
                break  # 더 이상 진전 없음 (남은 것들은 의존성 밖 문제)
            remaining = still_failed
    except Exception:
        pass


def _stub_legacy_langchain():
    """paddlex(RAG 리트리버 컴포넌트, 우리는 안 씀)가 langchain 1.0 이전 API
    (langchain.docstore.document.Document / langchain.text_splitter.*)를
    import하는데, 이 프로젝트엔 신버전 langchain(다른 기능용)이 깔려있어서
    모듈 자체가 없다. 실제로 쓰지 않는 기능이라 최소 스텁만 등록해 통과시킨다."""
    import sys
    import types

    if "langchain.docstore.document" not in sys.modules:
        doc_mod = types.ModuleType("langchain.docstore.document")

        class Document:  # noqa: N801
            def __init__(self, page_content="", metadata=None, **_kw):
                self.page_content = page_content
                self.metadata = metadata or {}

        doc_mod.Document = Document
        sys.modules["langchain.docstore"] = types.ModuleType("langchain.docstore")
        sys.modules["langchain.docstore.document"] = doc_mod

    if "langchain.text_splitter" not in sys.modules:
        import langchain_text_splitters

        ts_mod = types.ModuleType("langchain.text_splitter")
        ts_mod.RecursiveCharacterTextSplitter = langchain_text_splitters.RecursiveCharacterTextSplitter
        sys.modules["langchain.text_splitter"] = ts_mod


def _get_ocr_reader():
    global _ocr_reader

    if _ocr_reader is None:
        _preload_cuda_dlls()
        _stub_legacy_langchain()
        from paddleocr import PaddleOCR
        _ocr_reader = PaddleOCR(lang="korean", enable_mkldnn=False)

    return _ocr_reader


def detect_file_type(content):
    """파일 내용(bytes)의 매직바이트로 실제 형식 판별"""

    if content[:4] == b"%PDF":
        return "pdf"

    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "hwp"

    if content[:2] == b"PK":
        return "hwpx_or_zip"

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

    except Exception:
        return None


def extract_text_from_hwp(content):
    """구버전 HWP(OLE)에서 hwp5txt로 텍스트 추출"""

    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        result = subprocess.run(
            ["hwp5txt", tmp_path],
            capture_output=True,
            timeout=30
        )

        if result.returncode != 0:
            return None

        text = result.stdout.decode("utf-8", errors="ignore")

        return text if text.strip() else None

    except Exception:
        return None

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def extract_text_from_hwpx(content):
    """HWPX(zip+xml)에서 순수 파이썬으로 텍스트 추출"""

    try:
        texts = []

        with zipfile.ZipFile(io.BytesIO(content)) as z:
            section_files = sorted([
                n for n in z.namelist()
                if "section" in n.lower() and n.endswith(".xml")
            ])

            for section_file in section_files:
                xml_content = z.read(section_file).decode("utf-8", errors="ignore")
                matches = re.findall(r"<hp:t[^>]*>(.*?)</hp:t>", xml_content, re.DOTALL)

                for m in matches:
                    clean = re.sub(r"<[^>]+>", "", m)
                    if clean.strip():
                        texts.append(clean.strip())

        result = "\n".join(texts)

        return result if result.strip() else None

    except Exception:
        return None


def extract_text_from_scanned_pdf(content):
    """
    텍스트 레이어 없는 스캔 PDF를 OCR로 처리.
    품질이 완벽하진 않으니 최후 수단으로만 사용.
    """

    try:
        from pdf2image import convert_from_bytes
        import numpy as np

        images = convert_from_bytes(content, dpi=150)  # 메모리 문제로 150 고정
        reader = _get_ocr_reader()

        texts = []

        for img in images:
            result = reader.predict(np.array(img))
            for res in result:
                texts.extend(res["rec_texts"])

        result_text = "\n".join(texts)

        return result_text if result_text.strip() else None

    except Exception:
        return None


def get_notice_full_text(print_flpth_url):
    """
    printFlpthNm URL 하나를 받아 본문 텍스트를 추출.

    반환값: (텍스트 또는 None, 상태 메시지)
        "success_pdf" / "success_hwp" / "success_hwpx" / "success_ocr"
        "extract_failed" / "download_failed" / "unknown_format" / "no_url"
    """

    if not print_flpth_url or not print_flpth_url.strip():
        return None, "no_url"

    try:
        response = requests.get(print_flpth_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None, "download_failed"
        content = response.content
    except Exception:
        return None, "download_failed"

    file_type = detect_file_type(content)

    if file_type == "pdf":
        text = extract_text_from_pdf(content)
        if text:
            return text, "success_pdf"
        # 텍스트 레이어 없으면 스캔본으로 간주하고 OCR 시도
        text = extract_text_from_scanned_pdf(content)
        return (text, "success_ocr") if text else (None, "extract_failed")

    if file_type == "hwp":
        text = extract_text_from_hwp(content)
        return (text, "success_hwp") if text else (None, "extract_failed")

    if file_type == "hwpx_or_zip":
        text = extract_text_from_hwpx(content)
        return (text, "success_hwpx") if text else (None, "extract_failed")

    return None, "unknown_format"

def extract_text_from_scanned_pdf(content):
    try:
        from pdf2image import convert_from_bytes
        import numpy as np
        import gc

        images = convert_from_bytes(content, dpi=150)
        print(f"  [OCR진단] 페이지 수: {len(images)}")

        reader = _get_ocr_reader()

        texts = []

        for page_num, img in enumerate(images):
            img_array = np.array(img)
            print(f"  [OCR진단] {page_num+1}페이지 크기: {img_array.shape}")

            result = reader.predict(img_array)
            for res in result:
                texts.extend(res["rec_texts"])

            # 매 페이지 처리 후 메모리 명시적으로 정리
            del result
            gc.collect()

        result_text = "\n".join(texts)
        return result_text if result_text.strip() else None

    except Exception:
        return None