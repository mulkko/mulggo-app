"""K-Startup(창업진흥원) 지원사업 공고 정보 오픈 API 수집 스크립트.

data.go.kr 게이트웨이가 간헐적으로 504(Gateway Timeout)를 반환하므로
자동 재시도 + 백오프를 넣었다. 페이지를 넘겨가며 전체 공고를 받은 뒤
announcements_raw_kstartup 테이블에 저장한다.
  - 마감 공고(접수마감일이 지났거나 모집진행여부='N')는 저장하지 않는다.
  - pbanc_sn 기준으로 이미 있는 건은 건너뛴다.
"""

import json
import os
import re
import time
from datetime import date
from urllib.parse import unquote

import requests
from dotenv import load_dotenv
from psycopg2.extras import execute_values
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.db.connection import get_connection

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
# 스케줄러(작업 스케줄러 등)가 임의의 작업 디렉터리에서 실행해도 .env를 찾도록 경로 고정
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

SERVICE_KEY = os.getenv("KStartup_API_KEY")
BASE_URL = (
    "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
)

PAGE_SIZE = 100
REQUEST_TIMEOUT = 30          # 초. 성공 시 3초 내외지만 서버가 느릴 때를 대비
SLEEP_BETWEEN_PAGES = 0.5     # 초. 연속 호출 시 게이트웨이 부하 완화
MAX_RETRIES = 6              # 페이지당 상위 재시도 횟수(가시적 로그)

# API 응답 키 -> DB 컬럼명. 이름이 다른 것만 매핑에 신경 쓰면 되고,
# 나머지는 API 키와 DB 컬럼명이 동일하다.
#   - API "id"는 다운로드 순번(1,2,3...)이라 저장하지 않는다. pbanc_sn이 실제 공고번호.
#   - API "aply_mthd_etc_istc" 만 DB에서 "aply_mthd_etc" 로 짧다.
TEXT_COLUMNS = [
    "biz_pbanc_nm",
    "intg_pbanc_biz_nm",
    "pbanc_ctnt",
    "pbanc_ntrp_nm",
    "sprv_inst",
    "biz_prch_dprt_nm",
    "supt_biz_clsfc",
    "supt_regin",
    "aply_trgt",
    "aply_trgt_ctnt",
    "aply_excl_trgt_ctnt",
    "biz_trgt_age",
    "biz_enyy",
    "prfn_matr",
    "biz_aply_url",
    "biz_gdnc_url",
    "detl_pg_url",
    "prch_cnpl_no",
    "aply_mthd_eml_rcpt_istc",
    "aply_mthd_fax_rcpt_istc",
    "aply_mthd_vst_rcpt_istc",
    "aply_mthd_onli_rcpt_istc",
    "aply_mthd_pssr_rcpt_istc",
]

# INSERT 컬럼 순서 (source_raw, collected_at 은 코드에서 별도로 채운다)
INSERT_COLUMNS = [
    "pbanc_sn",
    *TEXT_COLUMNS,
    "aply_mthd_etc",       # API: aply_mthd_etc_istc
    "intg_pbanc_yn",       # "Y"/"N" -> boolean
    "rcrt_prgs_yn",        # "Y"/"N" 원문 그대로 (character(1))
    "pbanc_rcpt_bgng_dt",  # "YYYYMMDD" -> date
    "pbanc_rcpt_end_dt",
    "source_raw",          # 응답 원본 JSON 전체
]


def _build_session() -> requests.Session:
    """504/502/503 및 연결·읽기 타임아웃에 대해 지수 백오프로 재시도하는 세션."""
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1,               # 저수준 재시도 대기: 0, 1, 2초
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_announcements(session: requests.Session, num_rows: int, page: int) -> dict:
    if not SERVICE_KEY:
        raise ValueError("KStartup_API_KEY가 .env에 설정되어 있지 않습니다.")

    params = {
        # data.go.kr 서비스키는 이미 URL-인코딩된 값으로 발급되므로,
        # 미리 디코딩해 requests가 한 번만 인코딩하게 한다 (이중 인코딩 시 401 발생).
        "serviceKey": unquote(SERVICE_KEY),
        "page": page,
        "perPage": num_rows,
        "returnType": "json",
    }

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as err:
            last_err = err
            wait = min(2 ** attempt, 32)
            print(
                f"  [재시도] page={page} 시도 {attempt}/{MAX_RETRIES} 실패: "
                f"{type(err).__name__} → {wait}초 후 재시도"
            )
            time.sleep(wait)

    # last_err 문자열에 serviceKey가 들어간 요청 URL이 섞여 나오므로 마스킹 후 노출한다.
    reason = re.sub(r"serviceKey=[^&\s]+", "serviceKey=***", str(last_err))
    raise RuntimeError(
        f"page={page} 다운로드 실패 (재시도 {MAX_RETRIES}회 초과): "
        f"{type(last_err).__name__}: {reason}"
    )


def fetch_announcements_all(page_size: int = PAGE_SIZE) -> list:
    """페이지를 넘겨가며 전체 공고(totalCount)를 모두 받아올 때까지 반복 호출한다."""
    session = _build_session()
    items = []
    page = 1
    total_count = None

    while total_count is None or len(items) < total_count:
        result = fetch_announcements(session, num_rows=page_size, page=page)
        page_items = result.get("data", [])

        if not page_items:
            break

        items.extend(page_items)
        total_count = result.get("totalCount", 0)
        print(f"  page {page}: 누적 {len(items)}/{total_count}건")
        page += 1
        time.sleep(SLEEP_BETWEEN_PAGES)

    return items


def _clean(value):
    """빈 문자열/공백은 NULL 로 저장한다."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_bool(value):
    """'Y'/'N' -> True/False. 그 외에는 NULL."""
    text = _clean(value)
    if text is None:
        return None
    upper = text.upper()
    if upper in ("Y", "YES", "TRUE", "1"):
        return True
    if upper in ("N", "NO", "FALSE", "0"):
        return False
    return None


def _parse_date(value):
    """'YYYYMMDD' 또는 'YYYY-MM-DD' -> 'YYYY-MM-DD'. 형식이 안 맞으면 NULL."""
    text = _clean(value)
    if text is None:
        return None
    digits = text.replace("-", "").replace(".", "").replace("/", "")
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return None


def _is_closed(item: dict) -> bool:
    """마감 공고 판정.

    - 접수마감일(pbanc_rcpt_end_dt)이 오늘보다 이전이면 마감
    - 또는 모집진행여부(rcrt_prgs_yn)가 'N'이면 마감
    마감일이 없는(NULL) 공고는 상시/미정으로 보고 마감으로 치지 않는다.
    """
    prgs = _clean(item.get("rcrt_prgs_yn"))
    if prgs and prgs.upper() == "N":
        return True

    end_dt = _parse_date(item.get("pbanc_rcpt_end_dt"))  # 'YYYY-MM-DD' (ISO 문자열은 사전순=날짜순)
    if end_dt is not None and end_dt < date.today().isoformat():
        return True

    return False


def _build_row(item: dict) -> tuple | None:
    """API 응답 1건 -> INSERT_COLUMNS 순서의 값 튜플. 필수값 없으면 None 반환(건너뜀)."""
    pbanc_sn = _clean(item.get("pbanc_sn"))
    biz_pbanc_nm = _clean(item.get("biz_pbanc_nm"))
    if not pbanc_sn or not biz_pbanc_nm:
        return None

    values = [pbanc_sn]
    values.extend(_clean(item.get(col)) for col in TEXT_COLUMNS)
    values.append(_clean(item.get("aply_mthd_etc_istc")))
    values.append(_parse_bool(item.get("intg_pbanc_yn")))
    values.append(_clean(item.get("rcrt_prgs_yn")))
    values.append(_parse_date(item.get("pbanc_rcpt_bgng_dt")))
    values.append(_parse_date(item.get("pbanc_rcpt_end_dt")))
    values.append(json.dumps(item, ensure_ascii=False))
    return tuple(values)


def save_to_db(items: list) -> dict:
    """announcements_raw_kstartup 테이블에 '현재 진행 중인' 신규 공고만 저장.

    - 마감 공고(_is_closed)는 애초에 저장하지 않는다.
    - pbanc_sn 기준으로 이미 있는 건 건너뛴다 (bizinfo_api.save_to_db 와 동일한 방식).
    반환: {"inserted", "closed", "existing", "invalid"} 건수 요약.
    """
    summary = {"inserted": 0, "closed": 0, "existing": 0, "invalid": 0}
    if not items:
        return summary

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT pbanc_sn FROM announcements_raw_kstartup")
        existing_ids = {row[0] for row in cursor.fetchall()}

        rows = []
        seen = set()
        for item in items:
            if _is_closed(item):
                summary["closed"] += 1
                continue
            row = _build_row(item)
            if row is None:
                summary["invalid"] += 1
                continue
            pbanc_sn = row[0]
            if pbanc_sn in existing_ids or pbanc_sn in seen:
                summary["existing"] += 1
                continue
            seen.add(pbanc_sn)
            rows.append(row)

        if rows:
            column_list = ", ".join(INSERT_COLUMNS)
            execute_values(
                cursor,
                f"""
                INSERT INTO announcements_raw_kstartup ({column_list}, collected_at)
                VALUES %s
                """,
                rows,
                template="(" + ", ".join(["%s"] * len(INSERT_COLUMNS)) + ", NOW())",
            )
            connection.commit()

        summary["inserted"] = len(rows)
        return summary
    finally:
        connection.close()


def main():
    items = fetch_announcements_all()

    print(f"\n=== 수신 건수: {len(items)} ===")
    if items:
        print("=== 첫 번째 항목 필드 ===")
        print(list(items[0].keys()))

    summary = save_to_db(items)
    print(
        "\n=== DB 저장 결과 (announcements_raw_kstartup) ===\n"
        f"  신규 저장: {summary['inserted']}건\n"
        f"  마감 제외: {summary['closed']}건\n"
        f"  기존 중복: {summary['existing']}건\n"
        f"  필수값 누락: {summary['invalid']}건"
    )


if __name__ == "__main__":
    main()
