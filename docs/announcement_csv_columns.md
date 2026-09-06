# announcements 통합 컬럼 매핑 (2026-09-05)

`컬럼명.xlsx`(DB 설계 기준 컬럼 27개)를 기준으로, 지금 있는 bizinfo API +
전처리 파이프라인(`backend/preprocessing/pipeline.py`)만으로 각 컬럼을
채울 수 있는지 확인하고, 테스트용 CSV(`data/announcements_test_50.csv`)를
생성할 때 각 컬럼에 실제로 어떤 값을 넣었는지 정리한 문서입니다.

## 1. 지금 바로 채운 컬럼

| 컬럼명 | 값 출처 |
|---|---|
| `source` | 고정값 `"bizinfo"` |
| `raw_bizinfo_id` | bizinfo API `pblancId` |
| `title` | bizinfo API `pblancNm` |
| `content` | `pipeline.process_notice()`가 첨부파일(PDF/HWP/이미지)에서 추출한 원문 전체 텍스트 |
| `host_org_name` | bizinfo API `excInsttNm`(실제 사업을 수행/게시하는 기관) |
| `supervising_org` | bizinfo API `jrsdInsttNm`(소관/상급 기관) |
| `contact` | bizinfo API `refrncNm` |
| `category` | bizinfo API `pldirSportRealmLclasCodeNm`(대분류) + `pldirSportRealmMlsfcCodeNm`(중분류)를 `" > "`로 연결 |
| `target_summary` | bizinfo API `trgetNm` |
| `apply_start_date` / `apply_end_date` | bizinfo API `reqstBeginEndDe`("YYYY-MM-DD ~ YYYY-MM-DD")를 `~` 기준으로 분리 |
| `apply_method` | bizinfo API `reqstMthPapersCn` |
| `detail_page_url` | bizinfo API `pblancUrl` |
| `regions` | `pipeline`의 `region_list`(지원지역 목록)를 JSON 배열 문자열로 변환 |
| `region_status` | `pipeline`의 `region_status` 그대로 |
| `ksic_codes_matched` | `pipeline`의 `확정코드`를 JSON 배열 문자열로 변환 |
| `ksic_names_matched` | `pipeline`의 `확정업종명`을 JSON 배열 문자열로 변환 |
| `ksic_codes_excluded` | `pipeline`의 `제외코드`를 JSON 배열 문자열로 변환 (아래 "이번에 코드로 추가한 것" 참고) |
| `ksic_status` | `pipeline`의 `확정단계` 그대로 |
| `raw_kstartup_id` | bizinfo 소스라 이번 테스트에선 항상 빈 값(정상 — K-Startup 데이터를 받을 때만 채워짐) |

## 2. 이번에 코드로 새로 추가한 것

- **`ksic_codes_excluded`용 `제외코드` 필드** — `backend/ml/classifier/explicit_match.py`의
  `match_ksic_by_name()`은 원래부터 "제외업종"(제외 문맥에서 매칭된 업종)을
  계산해서 반환하고 있었는데, `backend/preprocessing/pipeline.py`의
  `process_bizinfo_notice()`가 최종 결과에서 이 값을 빼먹고 있었음. 이번에
  `pipeline.py`에 `"제외코드"` 키로 포함시키도록 수정함(2026-09-05).
- **`region_needs_review`** — 업종은 `업종_확인필요` 필드가 있었지만 지역은
  이런 판정이 없었음. `region_status`가 `inferred_`로 시작하거나
  `"unparsed"`면 `True`(확인필요), 그 외엔 `False`로 CSV 생성 스크립트
  (`backend/preprocessing/build_announcement_csv.py`)에서 새로 계산함.
- **`collected_at` / `updated_at`** — 크롤러(`bizinfo_api.py`)가 이 값을
  안 남기고 있어서, CSV 생성 스크립트가 실행 시각(`datetime.now()`)을
  두 컬럼에 동일하게 채워 넣음. 실제 DB 연동 시에는 INSERT 시점에 DB가
  채우는 게 맞고, 재수집으로 레코드가 갱신될 때만 `updated_at`이 달라져야 함.

## 3. 지금은 자리만 만들어두고 비워둔 것 (사용자 결정, 2026-09-05)

| 컬럼명 | 처리 | 사유 (나중에 다시 볼 것) |
|---|---|---|
| `announcement_id` | **1번부터 순번**(1, 2, 3, ...) | 여러 출처(bizinfo/K-Startup)를 아우르는 통합ID 규칙이 아직 미정. 규칙 확정되면 이 컬럼 채우는 로직을 교체해야 함. |
| `target_age_groups`(대상연령) | **빈 값(null)** | bizinfo API엔 이 정보가 없음. 다른 API(K-Startup 등)에는 있을 수 있어서, 그쪽 연동 시 해당 소스 데이터로 채워야 함. |
| `business_age_condition`(업력조건 원문) | **빈 값(null)** | 위와 동일한 이유 — bizinfo API엔 없고 다른 API 쪽 정보. |
| `management_no`(중복공고관리번호) | **빈 값(null)** | 여러 API에서 같은 공고가 중복 게시되는 걸 찾아서 묶는 용도인데, 그 중복판별 로직 자체가 아직 없음. 로직이 생기면 이 컬럼을 채워야 함. |

**주의**: 이 3가지는 전부 "지금 코드로는 못 채운다"가 아니라 "규칙이 아직
결정 안 됐다"는 뜻입니다. 규칙이 정해지면 이 문서와
`backend/preprocessing/build_announcement_csv.py`를 같이 업데이트하세요.

## 4. 생성 스크립트

`backend/preprocessing/build_announcement_csv.py` — bizinfo API에서 N건을
받아와 `pipeline.process_notice()`로 처리한 뒤, 위 매핑대로 27개 컬럼
CSV를 만듭니다. 기본 출력 위치: `data/announcements_test_50.csv`.

```
python -m backend.preprocessing.build_announcement_csv --count 50
```
