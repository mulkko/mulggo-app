"""
HWP -> HWPX 일괄 변환 (한컴오피스 '한글' COM 자동화 / Windows 전용)

[왜 필요한가]
  신청서 자동입력(biz_cert_ocr.fill_hwpx)은 HWPX(zip+XML)만 다룰 수 있다.
  정부 공고 첨부 신청서는 대개 구형 HWP라서 먼저 HWPX로 바꿔야 한다.

[어디서 실행하나]
  배포 API 서버(리눅스)에는 '한글'이 없다. 이 스크립트는 데이터 준비 단계에서
  Windows + 한컴오피스 '한글'이 설치된 PC에서 한 번 돌려 HWPX를 만들어 저장해 두고,
  런타임에는 저장된 HWPX를 채우는 식으로 쓴다. (런타임 변환 X)

[필요 조건]
  - Windows
  - 한컴오피스 '한글' 2018 이상 (COM Version 10.x+).
    ※ 한글 2010(8.x) / NEO(9.x) 는 자동화로 HWPX 저장이 안 됨(SaveAs가 False 반환).
      이 경우 rhwp.kr 수동 변환 또는 LibreOffice+H2Orestart 를 쓸 것.
  - pip install pywin32
  - 보안 팝업을 없애려면 FilePathCheckerModule 등록 필요 (아래 [보안모듈] 참고)

[사용]
  python -m backend.assistant.hwp_to_hwpx 신청서.hwp
  python -m backend.assistant.hwp_to_hwpx 신청서.hwp -o out/신청서.hwpx
  python -m backend.assistant.hwp_to_hwpx --out-dir converted forms/*.hwp

[보안모듈]
  한글은 자동화로 파일을 열/저장할 때 보안 대화상자를 띄운다. 아래 중 하나로 해제:
    1) pip install pyhwpx  (설치 시 FilePathCheckerModule.dll 자동 등록)
    2) 직접 dll 등록 후 이 스크립트 실행
  등록 안 돼 있으면 파일마다 '허용' 클릭이 필요하다(대량 변환 시 비현실적).
"""

import argparse
import glob
import os
import zipfile


def _make_hwp(visible: bool = False):
    import win32com.client as win32

    hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
    try:
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception:
        # 보안모듈 미등록 -> 파일 열기/저장 시 보안 팝업이 뜰 수 있음
        pass
    try:
        hwp.XHwpWindows.Item(0).Visible = visible
    except Exception:
        pass

    try:
        major = int(str(hwp.Version).split(",")[0])
        if major < 10:
            raise RuntimeError(
                f"이 한글 버전({hwp.Version})은 자동화 HWPX 저장을 지원하지 않습니다. "
                "한글 2018+ 필요. rhwp.kr 수동 변환 또는 LibreOffice+H2Orestart 사용."
            )
    except (ValueError, AttributeError):
        pass
    return hwp


def convert_one(hwp, hwp_path: str, out_path: str | None = None) -> str:
    """열린 Hwp 인스턴스로 파일 하나를 HWPX로 변환. 저장된 경로 반환."""
    hwp_path = os.path.abspath(hwp_path)
    if not os.path.exists(hwp_path):
        raise FileNotFoundError(hwp_path)
    if out_path is None:
        out_path = os.path.splitext(hwp_path)[0] + ".hwpx"
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if not hwp.Open(hwp_path, "", "forceopen:true"):
        raise RuntimeError(f"열기 실패: {hwp_path}")
    hwp.SaveAs(out_path, "HWPX", "")
    hwp.Clear(1)  # 저장 없이 현재 문서 비우기

    if not zipfile.is_zipfile(out_path):
        raise RuntimeError(f"변환 결과가 HWPX(zip)가 아님: {out_path}")
    return out_path


def convert(paths: list[str], out_dir: str | None = None, out_path: str | None = None) -> list[str]:
    """여러 HWP를 HWPX로 변환. 한글 인스턴스는 한 번만 띄운다."""
    hwp = _make_hwp()
    results = []
    try:
        for p in paths:
            if out_path is not None:
                dst = out_path
            elif out_dir is not None:
                dst = os.path.join(out_dir, os.path.splitext(os.path.basename(p))[0] + ".hwpx")
            else:
                dst = None
            results.append(convert_one(hwp, p, dst))
    finally:
        hwp.Quit()
    return results


def main():
    parser = argparse.ArgumentParser(description="HWP -> HWPX 변환 (Windows + 한컴오피스 한글)")
    parser.add_argument("inputs", nargs="+", help="HWP 파일 경로 (glob 패턴 가능)")
    parser.add_argument("-o", "--out", help="출력 파일 경로 (입력이 하나일 때)")
    parser.add_argument("--out-dir", help="출력 디렉터리 (입력이 여러 개일 때)")
    args = parser.parse_args()

    paths = []
    for pat in args.inputs:
        hits = glob.glob(pat)
        paths.extend(hits if hits else [pat])

    if args.out and len(paths) != 1:
        parser.error("--out 은 입력이 정확히 하나일 때만 사용하세요. 여러 개는 --out-dir 사용.")

    for src in convert(paths, out_dir=args.out_dir, out_path=args.out):
        print(f"[ok] {src}")


if __name__ == "__main__":
    main()
