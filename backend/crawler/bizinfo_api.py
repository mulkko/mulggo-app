# 기업마당(bizinfo) 지원사업정보 API 수집 스크립트
# 페이지를 넘기면서 전체 공고를 다 받은 뒤 data/bizinfo_sample.csv로 저장한다.

import csv
import os

import requests
from dotenv import load_dotenv

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


if __name__ == "__main__":
    items = fetch_all(PAGE_UNIT)
    save_to_csv(items, OUTPUT_PATH)
    print(f"{len(items)}건 수집 완료 -> {OUTPUT_PATH}")
