# 기업마당(bizinfo) 지원사업정보 API 수집 스크립트
# 페이지를 넘기면서 전체 공고를 다 받은 뒤 data/bizinfo_sample.csv로 저장한다.

import csv
import json
import os

import requests
from dotenv import load_dotenv

from backend.db.connection import get_connection

load_dotenv()

BIZINFO_API_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
API_KEY = os.getenv("BIZINFO_API_KEY")

PAGE_UNIT = 100

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
OUTPUT_PATH = os.path.join(DATA_DIR, "bizinfo.csv")


def fetch_page(page_index: int, page_unit: int) -> dict:
    if not API_KEY:
        raise RuntimeError("BIZINFO_API_KEY가 .env에 설정되어 있지 않습니다.")

    params = {
        "crtfcKey": API_KEY,
        "dataType": "json",
        "pageUnit": page_unit,
        "pageIndex": page_index,
    }

    response = requests.get(BIZINFO_API_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_all(page_unit: int = PAGE_UNIT) -> list:
    items = []
    page_index = 1

    while True:
        data = fetch_page(page_index, page_unit)
        page_items = data.get("jsonArray", [])
        if isinstance(page_items, dict):
            page_items = [page_items]

        if not page_items:
            break

        items.extend(page_items)

        total_count = int(page_items[0].get("totCnt", 0) or 0)
        if total_count and len(items) >= total_count:
            break

        page_index += 1

    return items


def save_to_csv(items: list, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fieldnames = []
    for item in items:
        for key in item.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


def save_to_db(items: list) -> int:
    """announcements_raw_bizinfo 테이블에 신규 공고만 저장. pblanc_id 기준으로 이미 있는 건 건너뜀."""
    if not items:
        return 0

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT pblanc_id FROM announcements_raw_bizinfo")
        existing_ids = {row[0] for row in cursor.fetchall()}

        new_items = [item for item in items if item.get("pblancId") not in existing_ids]

        for item in new_items:
            cursor.execute(
                """
                INSERT INTO announcements_raw_bizinfo (
                    pblanc_id, pblanc_nm, trget_nm, jrsd_instt_nm, exc_instt_nm,
                    bsns_sumry_cn, pldir_sport_realm_lclas_code_nm, pldir_sport_realm_mlsfc_code_nm,
                    reqst_begin_end_de, reqst_mth_papers_cn, hashtags, pblanc_url,
                    rcept_engn_hmpg_url, file_nm, print_flpth_nm, print_file_nm, flpth_nm,
                    inqire_co, creat_pnttm, updt_pnttm, source_raw, collected_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                """,
                (
                    item.get("pblancId"),
                    item.get("pblancNm"),
                    item.get("trgetNm"),
                    item.get("jrsdInsttNm"),
                    item.get("excInsttNm"),
                    item.get("bsnsSumryCn"),
                    item.get("pldirSportRealmLclasCodeNm"),
                    item.get("pldirSportRealmMlsfcCodeNm"),
                    item.get("reqstBeginEndDe"),
                    item.get("reqstMthPapersCn"),
                    item.get("hashtags"),
                    item.get("pblancUrl"),
                    item.get("rceptEngnHmpgUrl"),
                    item.get("fileNm"),
                    item.get("printFlpthNm"),
                    item.get("printFileNm"),
                    item.get("flpthNm"),
                    int(item["inqireCo"]) if item.get("inqireCo") not in (None, "") else None,
                    item.get("creatPnttm") or None,
                    item.get("updtPnttm") or None,
                    json.dumps(item, ensure_ascii=False),
                ),
            )

        connection.commit()
        return len(new_items)
    finally:
        connection.close()


if __name__ == "__main__":
    items = fetch_all(PAGE_UNIT)
    save_to_csv(items, OUTPUT_PATH)
    inserted = save_to_db(items)
    print(f"{len(items)}건 수집 완료 -> {OUTPUT_PATH} / DB 신규 저장 {inserted}건")
