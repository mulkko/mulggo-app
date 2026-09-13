# 공고 매칭 리스트 조회 API.
# FilterPage(기업유형/지원분야/업력/연령) 4개 그룹 전부 쿼리 파라미터로 연동됨.

import os
import tempfile
from datetime import date

import requests
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse, JSONResponse

from backend.assistant.hwpx_fill import fill_hwpx_all
from backend.assistant.pipeline import _load_mapping
from backend.auth.session import get_current_user_id, get_optional_user_id
from backend.db.connection import get_connection

router = APIRouter(prefix="/api/matching", tags=["matching"])


def _lookup_profile_ksic_code(conn, user_id: int) -> str | None:
    """로그인한 user_id 본인이 사업자등록증에서 확정한 KSIC 코드. 없으면(프로필/등록증
    미등록, 업종 미확정) None - 호출부는 이 경우 ksic 필터 없이(전체 공고) 보여준다."""
    cur = conn.cursor()
    cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if row is None:
        return None
    cur.execute(
        "SELECT ksic_code FROM profile_business_types "
        "WHERE profile_id = %s AND ksic_code IS NOT NULL ORDER BY is_primary DESC LIMIT 1",
        (row[0],),
    )
    row = cur.fetchone()
    return row[0] if row else None

DEFAULT_LIMIT = 20
MAPPING_XLSX = os.path.join("data", "field_mapping.xlsx")


def _format_dday(apply_end_date: date | None) -> str:
    if apply_end_date is None:
        return "상시모집"
    remaining = (apply_end_date - date.today()).days
    if remaining < 0:
        return "마감"
    return f"모집중 D-{remaining}"


SORT_OPTIONS = {
    # [2026-09-09 수정] 그냥 apply_end_date ASC만 하면 이미 지난 마감일이 날짜가
    # 빠르다는 이유로 맨 위로 옴("마감임박"인데 이미 마감된 게 1등) - 실측 확인.
    # 안 지난 것(false=0) 먼저, 그중 임박한 순, 그다음 지난 것(true=1) 순.
    # NULL(상시모집 등 마감일 없음)은 Postgres 기본 정렬 규칙상 ASC 맨 뒤로 감
    # - 두 정렬 기준 다 마찬가지라 결과적으로 맨 마지막.
    #
    # [2026-09-10 수정] 끝에 announcement_id를 2차 정렬로 추가함. collected_at은
    # 배치 크롤 시각이라 동점이 매우 흔하고(실측: 활성 공고 1,764건 중 distinct
    # collected_at이 5개뿐, 한 그룹이 1,417건), apply_end_date도 "상시모집"(NULL)
    # 922건이 전부 동점 - 정렬 기준에 동점이 있으면 Postgres가 쿼리마다 순서를
    # 다르게 줄 수 있어서, "더보기" 페이지네이션(LIMIT/OFFSET)이 같은 행을 다시
    # 보여주거나 건너뛰는 문제가 있었음. 유니크한 announcement_id를 마지막
    # 기준으로 추가해서 동점을 완전히 없애 순서를 고정한다.
    "deadline": "(apply_end_date < CURRENT_DATE) ASC, apply_end_date ASC, announcement_id DESC",
    "recent": "collected_at DESC, announcement_id DESC",
}


def _fetch_announcement_page(conn, where_sql: str, params: list, order_sql: str, limit: int, offset: int) -> tuple[list, bool, int]:
    """공통 조회 로직 - COUNT + "더보기"용 limit+1건 조회. list_announcements()가 매칭
    섹션/업종무관 섹션 양쪽에 그대로 재사용한다(2026-09-12, 두 섹션 분리 - 사용자 확인)."""
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM announcements {where_sql}", params)
    total = cur.fetchone()[0]
    cur.execute(
        f"""
        SELECT a.announcement_id, a.host_org_name, a.title, a.apply_end_date,
               a.ksic_codes_matched,
               EXISTS (
                   SELECT 1 FROM announcement_attachments att
                   WHERE att.announcement_id = a.announcement_id
                     AND att.fillable_field_count > 0
               ) AS fillable
        FROM announcements a
        {where_sql}
        ORDER BY {order_sql}
        LIMIT %s OFFSET %s
        """,
        [*params, limit + 1, offset],
    )
    rows = cur.fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    data = [
        {
            "id": str(announcement_id),
            "agency": host_org_name or "기관명 미기재",
            "dday": _format_dday(apply_end_date),
            "title": title,
            # [2026-09-09] 해시태그 로직은 사용자가 직접 확인 중 - 우선 빈 배열로 둔다.
            "tags": [],
            "fillable": bool(fillable),
            # [임시, 2026-09-11] 매칭된 업종코드 확인용 - 화면에 agency 옆 노출.
            "ksicCodesMatched": ksic_codes_matched or [],
        }
        for announcement_id, host_org_name, title, apply_end_date, ksic_codes_matched, fillable in rows
    ]
    return data, has_more, total


@router.get("")
def list_announcements(
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
    unclassified_offset: int = 0,
    unclassified_limit: int = DEFAULT_LIMIT,
    ksic: str = "",
    region: str = "",
    company: str = "",
    biz_age: str = "",
    field: str = "",
    age: str = "",
    sort: str = "recent",
    user_id: int | None = Depends(get_optional_user_id),
) -> dict:
    """"더보기" 버튼 방식 페이지네이션. limit+1건을 조회해서, limit보다 많이
    돌아오면 다음 페이지가 더 있다는 뜻이므로 has_more=True로 알려준다.

    ksic: 콤마로 구분된 KSIC 코드 목록 (예: "C,01"). 넘기면 공고의
    ksic_codes_matched 배열과 하나라도 겹치는 것만 필터. [2026-09-09, 테스트용]
    지금은 업종 드롭다운에 전체 KSIC(1,200여개)가 아니라 실제로 매칭된 것 중
    자주 나오는 몇 개만 넣어서 필터링 자체가 되는지 확인하는 용도.
    [2026-09-11] 비워서 호출하고 로그인 상태면, 사용자가 사업자등록증에서 확정한
    ksic_code(profile_business_types)로 대신 채운다 - 프론트가 매번 안 넘겨도
    "내 업종 기준" 매칭이 되게. 그마저 없으면(미등록/미확정) 그냥 전체 공고.

    [2026-09-12, 사용자 확인] ksic_status가 "업종무관(기본값)"/"특정불가"인 공고는
    ksic_codes_matched가 항상 빈 배열이라(schema.sql 참고 - decide_industry()가 특정
    업종을 못 정했을 때의 값) 배열 겹침 조건(&&)에 절대 안 걸린다 - 특정 업종으로
    필터링할 때마다 이 두 상태(합쳐서 전체 공고의 절반 가까이, 실측 1,348건)가 통째로
    빠지고 있었음. "업종무관"은 어떤 업종에도 해당된다는 뜻이라 당연히 포함해야 하고,
    "특정불가"도 사용자 확인 후 같이 포함하기로 함(분류만 실패했을 뿐 실제 제한이
    없을 가능성이 높다고 판단).
    다만 "같은 목록에 섞어서" 보여주면 진짜 매칭된 공고가 묻혀 보이니(사용자 확인),
    ksic 필터가 있을 때는 응답을 두 섹션으로 분리한다 - data/has_more/total은 진짜
    매칭(ksic_codes_matched 겹침)만, unclassified/unclassified_has_more/
    unclassified_total은 업종무관·특정불가만. 각자 자기 offset/limit
    (unclassified_offset/unclassified_limit)으로 독립적으로 "더보기" 페이지네이션한다.
    ksic 필터가 없으면(전체 공고 보기) 나눌 기준 자체가 없으니 예전처럼 data 하나에
    전부 담고 unclassified는 내려주지 않는다.

    region: 콤마로 구분된 시/도 목록 (예: "서울특별시,경기도"). 공고의 regions
    배열과 하나라도 겹치는 것만 필터. regions는 시/군 단위까지만 있고 구 단위는
    없음(extract_region.py 팀 결정 - 오탐 위험 때문에 의도적으로 제외).

    company: 콤마로 구분된 기업유형 목록 (예: "소상공인,중소기업"). target_summary가
    그중 하나와 정확히 일치하는 것만 필터. bizinfo만 값이 있음(kstartup의
    target_summary는 자유 문장이라 이 필터 대상이 아님 - FilterPage.tsx 옵션도
    bizinfo distinct 값 기준으로 만들어져 있음).

    biz_age: 업력 값 하나 (예: "예비창업자", "3년미만", "업력무관"). business_age_condition에
    이 값이 부분 문자열로 포함되면 매칭("=" 아님, "LIKE '%값%'") - kstartup 원본이
    "예비창업자~3년미만"처럼 두 조건을 붙여서 한 값으로 주는 경우가 있어서, "예비창업자"만
    선택해도 "예비창업자~3년미만" 같은 공고가 같이 잡히게 하려는 의도(docs/filter_options_
    review_2026-09-09.xlsx 참고). bizinfo는 이 컬럼 자체가 항상 NULL이라 대상이 아님.

    field: 콤마로 구분된 지원분야 목록 (예: "사업화,정책자금"). announcements.category에
    이 값들 중 하나라도 부분 문자열로 포함되면 매칭(ILIKE ANY). kstartup은 category가
    "사업화"처럼 깨끗한 단일 값이라 그대로 매칭되고, bizinfo는 "창업 > 사업화지원"처럼
    "대분류 > 중분류" 합친 문자열이라 부분 매칭으로 대분류만 선택해도 잡히게 한다
    (docs/filter_options_review_2026-09-09.xlsx "지원분야" 시트 참고).

    age: 사업대상연령 값 하나 (예: "만 40세 이상", "전연령"). announcements.target_age_groups
    (배열, kstartup만 값 있음)와 겹치면 매칭. 실제 distinct 값 그대로 씀(가공된 버킷 없음)
    - docs/filter_options_review_2026-09-09.xlsx "target_age_groups" 시트 참고.

    sort: "recent"(기본, 최근 등록순) 또는 "deadline"(마감임박순)."""
    ksic_codes = [c.strip() for c in ksic.split(",") if c.strip()]
    regions = [r.strip() for r in region.split(",") if r.strip()]
    companies = [c.strip() for c in company.split(",") if c.strip()]
    fields = [f.strip() for f in field.split(",") if f.strip()]
    biz_age = biz_age.strip()
    age = age.strip()
    order_sql = SORT_OPTIONS.get(sort, SORT_OPTIONS["recent"])

    conn = get_connection()
    try:
        if not ksic_codes and user_id is not None:
            profile_ksic = _lookup_profile_ksic_code(conn, user_id)
            if profile_ksic:
                ksic_codes = [profile_ksic]

        # [2026-09-09] 이미 마감 지난 공고는 리스트에서 아예 뺀다. announcements 원본
        # 데이터는 안 지운다(raw/가공 원칙) - 여기 조회 조건에서만 제외. 마감일이
        # 없는(NULL, 상시모집 등) 공고는 계속 보여줌.
        # region/company/biz_age/field/age 조건은 매칭 섹션·업종무관 섹션 둘 다에
        # 똑같이 적용되므로 base_conditions로 공유한다.
        base_conditions = ["(apply_end_date IS NULL OR apply_end_date >= CURRENT_DATE)"]
        base_params: list = []
        if regions:
            base_conditions.append("regions && %s")
            base_params.append(regions)
        if companies:
            base_conditions.append("target_summary = ANY(%s)")
            base_params.append(companies)
        if biz_age:
            base_conditions.append("business_age_condition LIKE %s")
            base_params.append(f"%{biz_age}%")
        if fields:
            base_conditions.append("category ILIKE ANY(%s)")
            base_params.append([f"%{f}%" for f in fields])
        if age:
            base_conditions.append("target_age_groups && %s")
            base_params.append([age])

        if ksic_codes:
            matched_conditions = [*base_conditions, "ksic_codes_matched && %s"]
            matched_params = [*base_params, ksic_codes]
        else:
            matched_conditions = base_conditions
            matched_params = base_params
        matched_where_sql = "WHERE " + " AND ".join(matched_conditions)
        data, has_more, total = _fetch_announcement_page(conn, matched_where_sql, matched_params, order_sql, limit, offset)

        unclassified_data: list = []
        unclassified_has_more = False
        unclassified_total = 0
        if ksic_codes:
            # NOT (ksic_codes_matched && %s)는 안전장치 - 실제로는 업종무관/특정불가가
            # ksic_codes_matched를 항상 빈 배열로 두므로(위 독스트링 참고) 겹칠 일이
            # 없지만, 나중에 데이터가 달라져도 매칭 섹션과 절대 겹치지 않게 명시적으로 뺀다.
            unclassified_conditions = [
                *base_conditions,
                "ksic_status IN ('업종무관(기본값)', '특정불가')",
                "NOT (ksic_codes_matched && %s)",
            ]
            unclassified_params = [*base_params, ksic_codes]
            unclassified_where_sql = "WHERE " + " AND ".join(unclassified_conditions)
            unclassified_data, unclassified_has_more, unclassified_total = _fetch_announcement_page(
                conn, unclassified_where_sql, unclassified_params, order_sql, unclassified_limit, unclassified_offset,
            )
    finally:
        conn.close()

    response = {"success": True, "data": data, "has_more": has_more, "total": total}
    if ksic_codes:
        response["unclassified"] = unclassified_data
        response["unclassified_has_more"] = unclassified_has_more
        response["unclassified_total"] = unclassified_total
    return response


def _format_period(apply_start_date: date | None, apply_end_date: date | None) -> str:
    if apply_start_date and apply_end_date:
        return f"{apply_start_date:%m.%d} ~ {apply_end_date:%m.%d} 접수"
    if apply_end_date:
        return f"~{apply_end_date:%m.%d} 접수"
    return "상시모집"


def _format_dday_short(apply_end_date: date | None) -> str:
    if apply_end_date is None:
        return "상시모집"
    remaining = (apply_end_date - date.today()).days
    return "마감" if remaining < 0 else f"D-{remaining}"


def _fetch_docs(announcement_id: int, conn) -> list[dict]:
    """신청서류 목록. announcement_attachments는 지금 bizinfo 공고만 채워져 있음
    (kstartup 원본엔 첨부파일 정보 자체가 없어서 자연히 빈 리스트가 나옴).
    fillable: fillable_field_count > 0 (NULL/-1/0은 전부 False - 미확인·실패·매칭없음
    을 굳이 구분해서 보여줄 필요는 없고, 화면엔 "채울 수 있다/없다"만 필요).
    downloadUrl: 채우기 여부와 무관하게 원본 그대로 받아서 직접 작성할 수 있도록."""
    cur = conn.cursor()
    cur.execute(
        "SELECT attachment_id, file_name, source_url, fillable_field_count FROM announcement_attachments "
        "WHERE announcement_id = %s ORDER BY attachment_id",
        (announcement_id,),
    )
    return [
        {
            "attachmentId": attachment_id,
            "fileName": file_name,
            "fillable": bool(fillable_field_count and fillable_field_count > 0),
            "downloadUrl": source_url,
        }
        for attachment_id, file_name, source_url, fillable_field_count in cur.fetchall()
    ]


def _build_biz_cert_for_user(conn, user_id: int):
    """로그인한 user_id 본인의 사업자등록증 정보로 채운다.
    [2026-09-10] 이전엔 로그인 세션이 없어서 DB에 등록된 아무 사업자등록증 1건
    (profile_id=15, 명현정공)으로 고정 채우던 임시 코드였음 - 세션이 생겨서
    본인 profile_id 기준 조회로 교체.

    반환: (biz_cert dict, entity_type, profile_id) 또는 프로필/등록된 사업자등록증이
    없으면 None. profile_id는 호출부가 채우기 이력(applications)을 남길 때 같이 씀.
    """
    cur = conn.cursor()
    cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if row is None:
        return None
    profile_id = row[0]

    cur.execute(
        """
        SELECT entity_type_code, biz_no, corp_no, company_name, ceo_name,
               open_date, birth_date, business_address, head_address
        FROM biz_registration_docs WHERE profile_id = %s ORDER BY document_id DESC LIMIT 1
        """,
        (profile_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None

    (entity_type_code, biz_no, corp_no, company_name, ceo_name,
     open_date, birth_date, business_address, head_address) = row

    cur.execute(
        "SELECT business_category, business_item FROM profile_business_types "
        "WHERE profile_id = %s ORDER BY is_primary DESC LIMIT 1",
        (profile_id,),
    )
    cat_row = cur.fetchone()
    biz_type, biz_item = cat_row if cat_row else (None, None)

    entity_type = "법인" if entity_type_code == "corporate" else "개인"
    biz_cert = {
        "trade_name": company_name if entity_type == "개인" else "",
        "corp_name": company_name if entity_type == "법인" else "",
        "ceo_name": ceo_name or "",
        "biz_no": biz_no or "",
        "corp_no": corp_no or "",
        "birth_date": str(birth_date) if birth_date else "",
        "open_date": str(open_date) if open_date else "",
        "address_basic": (head_address or business_address) if entity_type == "법인" else (business_address or ""),
        "biz_type": biz_type or "",
        "biz_item": biz_item or "",
    }
    return biz_cert, entity_type, profile_id


# ============================================================
# [실험용, 2026-09-11] DocPreview.tsx "채워질 정보 미리보기" 카드용 - 사용자 확인 중,
# 반응 별로면 이 엔드포인트 통째로 지우고 프론트 카드도 같이 걷어내면 됨.
# _build_biz_cert_for_user()는 이미 fill_attachment()가 쓰던 것 그대로 재사용(재OCR 없음,
# DB에 저장된 값 SELECT만) - 실제 hwpx 채우기 전에 "이 정보로 채워집니다"만 보여주는 용도.
# ============================================================
@router.get("/biz-cert-preview")
def get_biz_cert_preview(user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    conn = get_connection()
    try:
        result = _build_biz_cert_for_user(conn, user_id)
    finally:
        conn.close()

    if result is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"message": "등록된 사업자등록증이 없습니다.", "code": "BIZ_CERT_NOT_FOUND"}},
        )

    biz_cert, entity_type, _ = result
    return JSONResponse(content={
        "success": True,
        "data": {
            "name": biz_cert["corp_name"] or biz_cert["trade_name"],
            "ceoName": biz_cert["ceo_name"],
            "bizNo": biz_cert["biz_no"],
            "address": biz_cert["address_basic"],
            "entityType": entity_type,
        },
    })
# ============================================================
# [실험용 끝]
# ============================================================


@router.get("/attachments/{attachment_id}/fill")
def fill_attachment(
    attachment_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
):
    """신청서류 원본을 받아서 로그인한 사용자 본인의 사업자등록증 정보로 채운 결과를
    파일로 돌려준다. 성공하면 applications에 이력만 남긴다(파일 자체는 저장 안 함 -
    마이페이지 "채우기 이용내역"에서 다시 누르면 이 엔드포인트를 재호출해 즉석
    재생성한다 - 사용자 확인, 2026-09-10)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT file_name, source_url, fillable_field_count FROM announcement_attachments "
            "WHERE attachment_id = %s",
            (attachment_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"success": False, "error": {"message": "첨부파일을 찾을 수 없습니다.", "code": "NOT_FOUND"}}
        file_name, source_url, fillable_field_count = row
        if not fillable_field_count or fillable_field_count <= 0:
            return {
                "success": False,
                "error": {"message": "이 서류는 자동채우기를 지원하지 않습니다.", "code": "NOT_FILLABLE"},
            }

        built = _build_biz_cert_for_user(conn, user_id)
        if built is None:
            return {
                "success": False,
                "error": {"message": "등록된 사업자등록증 정보가 없습니다.", "code": "NO_BIZ_CERT"},
            }
        biz_cert, entity_type, profile_id = built

        # [2026-09-10] 마감된 공고는 원본 첨부 URL이 언젠가 내려갈 수 있어서(실측:
        # 마감 며칠 이내는 아직 정상 응답 확인했지만 장기적으론 보장 안 됨), 네트워크
        # 예외를 그대로 500으로 터뜨리지 않고 깨끗한 에러로 감싼다.
        try:
            resp = requests.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            return {
                "success": False,
                "error": {
                    "message": "원본 첨부파일을 더 이상 받을 수 없어요. 공고 원문에서 직접 확인해주세요.",
                    "code": "SOURCE_UNAVAILABLE",
                },
            }

        fd, tmp_in = tempfile.mkstemp(suffix=".hwpx")
        os.close(fd)
        fd, tmp_out = tempfile.mkstemp(suffix=".hwpx")
        os.close(fd)
        try:
            with open(tmp_in, "wb") as f:
                f.write(resp.content)
            rules = _load_mapping(MAPPING_XLSX)
            fill_hwpx_all(tmp_in, tmp_out, rules, biz_cert, entity_type, models=None)
        finally:
            os.remove(tmp_in)

        cur.execute(
            "INSERT INTO applications (profile_id, attachment_id, exported_at, created_at) "
            "VALUES (%s, %s, now(), now())",
            (profile_id, attachment_id),
        )
        conn.commit()
    finally:
        conn.close()

    background_tasks.add_task(os.remove, tmp_out)
    out_name = os.path.splitext(file_name)[0] + "_채움.hwpx"
    # [2026-09-10] .hwpx는 파이썬 mimetypes가 모르는 확장자라 media_type 없이 두면
    # application/octet-stream으로 내려가서 브라우저 "흔치 않은 파일" 경고에 더 잘 걸림.
    # 한글이 쓰는 hwpx MIME을 명시해서 조금이라도 완화 - 매번 새로 채워지는 고유 파일이라
    # 경고 자체(크롬의 "한 번도 못 본 파일" 휴리스틱)는 이걸로도 완전히는 안 없어짐.
    return FileResponse(
        tmp_out,
        filename=out_name,
        media_type="application/haansofthwpx",
        background=background_tasks,
    )


@router.get("/{announcement_id}")
def get_announcement_detail(
    announcement_id: int, user_id: int | None = Depends(get_optional_user_id)
) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.title, a.content, a.host_org_name, a.supervising_org, a.target_summary,
                   a.apply_method, a.contact, a.apply_start_date, a.apply_end_date,
                   a.detail_page_url, b.hashtags
            FROM announcements a
            LEFT JOIN announcements_raw_bizinfo b ON b.raw_bizinfo_id = a.raw_bizinfo_id
            WHERE a.announcement_id = %s
            """,
            (announcement_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"success": False, "error": {"message": "공고를 찾을 수 없습니다.", "code": "NOT_FOUND"}}

        (title, content, host_org_name, supervising_org, target_summary,
         apply_method, contact, apply_start_date, apply_end_date,
         detail_page_url, raw_hashtags) = row

        # 해시태그는 기업마당(bizinfo) 원본에만 있는 필드 (K-Startup 원본엔 없음).
        # 원본은 "경영,전남광주,홍보시책" 처럼 콤마로만 구분돼있어 "#" 붙여서 공백으로 이어붙인다.
        hashtags = " ".join(f"#{t.strip()}" for t in (raw_hashtags or "").split(",") if t.strip())

        docs = _fetch_docs(announcement_id, conn)

        bookmarked = False
        if user_id is not None:
            cur.execute(
                "SELECT 1 FROM bookmarks WHERE user_id = %s AND announcement_id = %s",
                (user_id, announcement_id),
            )
            bookmarked = cur.fetchone() is not None
    finally:
        conn.close()

    agency = " · ".join(p for p in [host_org_name, supervising_org] if p) or "정보 없음"

    return {
        "success": True,
        "data": {
            "id": str(announcement_id),
            "period": _format_period(apply_start_date, apply_end_date),
            "dday": _format_dday_short(apply_end_date),
            "title": title,
            "hashtags": hashtags,
            "bookmarked": bookmarked,
            # [2026-09-09] 사용자 프로필(지역/업종) 연결 전까지는 진짜 개인화된 코멘트를
            # 만들 수 없다 - 근거 없는 맞춤 문구를 지어내지 않고 안내 문구로 대신한다.
            "aiComment": "맞춤 코멘트는 준비 중입니다.",
            "overview": [
                {"label": "소관기관 · 수행기관", "value": agency},
                {"label": "지원 대상", "value": target_summary or "정보 없음"},
                {"label": "신청 방법", "value": apply_method or "정보 없음"},
                {"label": "문의처", "value": contact or "정보 없음"},
            ],
            "content": content or "",
            "docs": docs,
            "homepageUrl": detail_page_url,
        },
    }


@router.post("/{announcement_id}/bookmark")
def add_bookmark(announcement_id: int, user_id: int = Depends(get_current_user_id)) -> dict:
    """찜하기. bookmarks에 (user_id, announcement_id) 유니크 제약이 없어서 INSERT 전에
    직접 존재 여부를 확인한다 - 중복 클릭해도 행이 여러 개 쌓이지 않게."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM bookmarks WHERE user_id = %s AND announcement_id = %s",
            (user_id, announcement_id),
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO bookmarks (user_id, announcement_id, bookmarked_at) VALUES (%s, %s, now())",
                (user_id, announcement_id),
            )
            conn.commit()
    finally:
        conn.close()
    return {"success": True, "data": {"bookmarked": True}}


@router.delete("/{announcement_id}/bookmark")
def remove_bookmark(announcement_id: int, user_id: int = Depends(get_current_user_id)) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM bookmarks WHERE user_id = %s AND announcement_id = %s",
            (user_id, announcement_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"success": True, "data": {"bookmarked": False}}
