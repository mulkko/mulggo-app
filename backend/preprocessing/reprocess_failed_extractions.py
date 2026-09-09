# backend/preprocessing/reprocess_failed_extractions.py
#
# [2026-09-09] 일회성 유지보수 스크립트. announcements(source='bizinfo')에
# 이미 저장된 행 중, 본문추출이 그때 당시 실패해서(주로 PaddleOCR
# oneDNN 버그) 원래 요약글(content == bsns_sumry_cn 정제본)로만 채워진
# 행만 골라서, extract_all_texts.py의 enable_mkldnn=False 수정 이후
# 다시 추출을 시도하고 성공한 것만 업데이트한다.
#
# 한 건씩 즉시 UPDATE + commit한다 - OCR 쪽에서 세그멘테이션 폴트(파이썬
# try/except로 못 잡는 네이티브 크래시)가 드물게 나는 걸 확인했는데,
# 배치 끝에 한 번에 저장하는 방식이면 크래시 시 그 실행 전체가 날아간다.
# 즉시 저장하면 중간에 죽어도 그때까지 처리한 건 안전하고, 다시 실행하면
# (아직도 요약글 그대로인 것만 다시 후보로 잡히므로) 자동으로 이어서 된다.

import json
import subprocess
import sys

from backend.db.connection import get_connection
from backend.preprocessing.sync_bizinfo_announcements import (
    _clean_html_field,
    _strip_nul,
)
from backend.ml.classifier.decide_industry import decide_industry


# [2026-09-09] 일부 스캔 이미지(raw_bizinfo_id=185, 322 등 실측 확인)에서
# PaddleOCR이 파이썬 try/except로 못 잡는 세그멘테이션 폴트를 낸다 -
# 어떤 파일이 걸릴지 미리 알 수 없어서 하나하나 예외 목록에 추가하는 대신,
# get_notice_full_text() 호출 자체를 별도 워커 프로세스(_ocr_worker.py)로
# 격리한다. 워커가 죽으면 그 건만 실패 처리하고 새 워커를 띄워 이어간다.


class OcrWorker:
    def __init__(self):
        self.proc = None

    def _ensure_alive(self):
        if self.proc is None or self.proc.poll() is not None:
            self.proc = subprocess.Popen(
                [sys.executable, "-m", "backend.preprocessing._ocr_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )

    def extract(self, url: str) -> tuple[str | None, str]:
        self._ensure_alive()
        try:
            self.proc.stdin.write(url + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise BrokenPipeError("워커가 응답 없이 종료됨(크래시 추정)")
            data = json.loads(line)
            return data["text"], data["status"]
        except Exception:
            # 워커가 죽었으니(세그폴트 등) 다음 호출에서 새로 띄우도록 정리.
            try:
                self.proc.kill()
            except Exception:  # noqa: BLE001
                pass
            self.proc = None
            return None, "worker_crashed"

    def close(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()


def find_candidates(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.raw_bizinfo_id, a.content, r.bsns_sumry_cn, r.pblanc_nm,
               r.hashtags, r.print_flpth_nm
        FROM announcements a
        JOIN announcements_raw_bizinfo r ON r.raw_bizinfo_id = a.raw_bizinfo_id
        WHERE a.source = 'bizinfo'
        ORDER BY a.raw_bizinfo_id
        """
    )
    rows = cur.fetchall()

    candidates = []
    for raw_id, content, raw_summary, pblanc_nm, hashtags, print_flpth_nm in rows:
        cleaned_summary = _clean_html_field(raw_summary)
        if (content or None) == (cleaned_summary or None):
            candidates.append({
                "raw_bizinfo_id": raw_id,
                "pblanc_nm": pblanc_nm,
                "hashtags": hashtags,
                "print_flpth_nm": print_flpth_nm,
            })
    return candidates


def run():
    conn = get_connection()
    candidates = find_candidates(conn)
    total = len(candidates)
    print(f"재처리 대상(본문추출 실패 추정): {total}건")

    worker = OcrWorker()
    improved = 0
    still_failed = 0
    for i, row in enumerate(candidates, start=1):
        raw_id = row["raw_bizinfo_id"]
        full_text, extract_status = worker.extract(row["print_flpth_nm"] or "")

        if not extract_status.startswith("success"):
            print(f"[{i}/{total}] raw_bizinfo_id={raw_id} 여전히 실패({extract_status})")
            still_failed += 1
            continue

        full_text = _strip_nul(full_text) or ""
        match_text = " | ".join(
            p for p in [row["pblanc_nm"] or "", row["hashtags"] or "", full_text] if p
        )
        # main 파이프라인(run())과 동일하게 LLM 폴백은 기본 꺼둔다 -
        # decide_industry() 자체 기본값은 True라 안 끄면 여기서만 LLM을
        # 호출하는 불일치(+예상 못한 비용)가 생긴다.
        result = decide_industry(match_text, use_llm_fallback=False) if match_text.strip() else None
        ksic_stage = result["확정단계"] if result else "특정불가"

        cur = conn.cursor()
        cur.execute(
            """
            UPDATE announcements
            SET content = %s,
                ksic_codes_matched = %s,
                ksic_names_matched = %s,
                ksic_codes_excluded = %s,
                ksic_status = %s
            WHERE source = 'bizinfo' AND raw_bizinfo_id = %s
            """,
            (
                _strip_nul(full_text),
                result["확정코드"] if result else [],
                result["확정업종명"] if result else [],
                [x["코드"] for x in (result.get("제외업종") or [])] if result else [],
                ksic_stage,
                raw_id,
            ),
        )
        conn.commit()
        improved += 1
        print(f"[{i}/{total}] raw_bizinfo_id={raw_id} 재추출 성공({extract_status}) -> 업데이트 완료 (업종분류: {ksic_stage})")

    worker.close()
    conn.close()
    print(f"\n완료: {improved}건 개선됨 / {still_failed}건 여전히 실패 / 총 {total}건")


if __name__ == "__main__":
    run()
