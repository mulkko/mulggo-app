# announcement_attachments 중 hwpx 파일이 실제로 "채우기"가 되는지 확인하는
# 일회성 스크립트. 파일당: 다운로드 -> data/field_mapping.xlsx 기준으로 더미
# 데이터를 채워보고 -> 몇 자리가 매칭됐는지 fillable_field_count에 저장한다.
#
# fillable_field_count: NULL=미확인, -1=열어보다 실패(진짜 hwpx가 아니거나 손상),
# 0 이상=매칭된 자리 수 (0이면 "형식은 hwpx인데 우리가 아는 라벨이 하나도 없음").
#
# 실행: python -m backend.preprocessing.check_attachment_fillable

import os
import tempfile

import requests

from backend.assistant.hwpx_fill import fill_hwpx_all
from backend.assistant.pipeline import _load_mapping
from backend.db.connection import get_connection

MAPPING_XLSX = os.path.join("data", "field_mapping.xlsx")

# 실제 값이 뭐든 상관없다 - 라벨이 몇 개나 "매칭되는지"만 확인하는 용도라
# 모든 매핑 key에 대응하는 더미 값을 채운다.
_DUMMY_BIZ_CERT = {
    "biz_no": "123-45-67890", "corp_no": "110111-1234567",
    "trade_name": "테스트상사", "corp_name": "테스트주식회사", "ceo_name": "홍길동",
    "birth_date": "1990-01-01", "open_date": "2020-01-01", "zip_code": "12345",
    "address_basic": "서울특별시 마포구 테스트로 1", "address_detail": "2층",
    "head_office_type": "본점", "biz_type": "제조업", "biz_item": "전자부품",
    "tax_email": "test@example.com", "issue_date": "2020-01-05",
    "tax_type": "일반과세자", "is_unit_taxation": "N",
}


def check_one(source_url: str) -> int:
    """반환: 매칭된 자리 수(0 이상), 실패하면 -1."""
    resp = requests.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()

    fd, tmp_in = tempfile.mkstemp(suffix=".hwpx")
    os.close(fd)
    fd, tmp_out = tempfile.mkstemp(suffix=".hwpx")
    os.close(fd)
    try:
        with open(tmp_in, "wb") as f:
            f.write(resp.content)
        rules = _load_mapping(MAPPING_XLSX)
        log = fill_hwpx_all(tmp_in, tmp_out, rules, _DUMMY_BIZ_CERT, "개인", models=None)
        return len(log)
    except Exception as e:
        print(f"    실패: {type(e).__name__}: {e}")
        return -1
    finally:
        for p in (tmp_in, tmp_out):
            try:
                os.remove(p)
            except OSError:
                pass


def run():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT attachment_id, source_url FROM announcement_attachments "
            "WHERE file_type = 'hwpx' AND fillable_field_count IS NULL"
        )
        rows = cur.fetchall()
        print(f"확인 대상 hwpx: {len(rows)}건")

        results = []
        for i, (attachment_id, source_url) in enumerate(rows, start=1):
            count = check_one(source_url)
            cur.execute(
                "UPDATE announcement_attachments SET fillable_field_count = %s WHERE attachment_id = %s",
                (count, attachment_id),
            )
            conn.commit()
            results.append(count)
            if i % 50 == 0:
                print(f"  진행: {i}/{len(rows)}")

        fillable = sum(1 for c in results if c > 0)
        zero = sum(1 for c in results if c == 0)
        failed = sum(1 for c in results if c == -1)
        print(f"완료. 채울 수 있음(1개 이상 매칭): {fillable}건 / "
              f"hwpx인데 매칭 0건: {zero}건 / 열기 실패: {failed}건")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
