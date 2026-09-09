# backend/preprocessing/_ocr_worker.py
#
# [2026-09-09] reprocess_failed_extractions.py 전용 워커 프로세스.
#
# 특정 스캔 이미지(예: raw_bizinfo_id=185, 322)에서 PaddleOCR이 파이썬
# try/except로 못 잡는 세그멘테이션 폴트를 내는 걸 실측 확인함 - 메인
# 프로세스에서 직접 OCR을 돌리면 크래시 한 번에 그때까지 처리한 나머지
# 전체 배치가 다 죽는다. 이 워커를 별도 프로세스로 띄워서 stdin으로
# URL을 한 줄씩 받아 처리하면, 이 프로세스가 죽어도 부모 프로세스는
# 안 죽고 "이번 건만 실패"로 처리한 뒤 새 워커를 다시 띄워 이어갈 수 있다.
#
# 프로토콜: stdin에서 한 줄(첨부 URL)을 읽어서 get_notice_full_text()
# 결과를 JSON 한 줄로 stdout에 쓰고 즉시 flush. EOF까지 반복.

import json
import sys

from backend.preprocessing.extract_all_texts import get_notice_full_text


def main():
    for line in sys.stdin:
        url = line.rstrip("\n")
        try:
            text, status = get_notice_full_text(url)
        except Exception as e:  # noqa: BLE001 - 워커 안에서 뭐가 터지든 부모에 결과로 전달
            text, status = None, f"worker_exception:{type(e).__name__}"
        print(json.dumps({"text": text, "status": status}), flush=True)


if __name__ == "__main__":
    main()
