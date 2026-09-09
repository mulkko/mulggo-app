# 이미 announcements에 저장된 bizinfo 공고에 신청서류 첨부(announcement_attachments)를
# 일회성으로 채워 넣는 백필 스크립트.
#
# sync_bizinfo_announcements.py에 첨부 채우기 로직(2026-09-09)이 추가되기 *전에*
# 이미 반영된 공고들은 첨부가 비어있다. 그 공고들을 처음부터 재동기화(첨부 재다운로드+
# 재추출+재분류)하지 않고, raw 테이블에 이미 있는 file_nm/flpth_nm만 가져와서
# announcement_attachments만 채운다 - 외부 네트워크 호출 없이 DB 안에서만 끝난다.
# 여러 번 실행해도 안전함(_replace_attachments가 DELETE 후 INSERT).
#
# 실행: python -m backend.preprocessing.backfill_bizinfo_attachments

from backend.db.connection import get_connection
from backend.preprocessing.sync_bizinfo_announcements import _replace_attachments


def run():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.announcement_id, r.file_nm, r.flpth_nm
            FROM announcements a
            JOIN announcements_raw_bizinfo r ON r.raw_bizinfo_id = a.raw_bizinfo_id
            WHERE a.source = 'bizinfo'
            """
        )
        rows = cur.fetchall()
        print(f"대상 공고: {len(rows)}건")

        for announcement_id, file_nm, flpth_nm in rows:
            _replace_attachments(cur, announcement_id, file_nm, flpth_nm)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM announcement_attachments")
        print(f"완료. announcement_attachments 총 {cur.fetchone()[0]}건")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
