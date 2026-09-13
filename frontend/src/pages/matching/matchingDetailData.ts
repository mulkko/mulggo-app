/**
 * 공고 상세(지원사업 상세) 화면 타입 정의.
 *
 * [2026-09-13] 예전엔 이 파일이 a1~a5 더미데이터(DUMMY_ANNOUNCEMENT_DETAILS +
 * getAnnouncementDetail())를 담고 있었다 - 백엔드 공고 상세 API(GET /api/matching/:id)가
 * 없던 시절 MatchingDetail.tsx가 화면에 뿌릴 값으로 썼던 것. 지금은 그 API가 실제로
 * 붙어 있어서 더미 함수는 어디서도 호출되지 않아 지웠고, MatchingDetail.tsx/DocPreview.tsx가
 * import type으로 재사용하는 타입 정의만 남긴다.
 */

export interface OverviewItem {
  /** 항목 라벨 (예: "소관기관 · 수행기관") */
  label: string;
  /** 항목 값 */
  value: string;
}

export interface RequiredDoc {
  /** announcement_attachments.attachment_id - 채우기 실행 API 호출에 씀 */
  attachmentId: number;
  /** 파일명 (확장자 포함, 길면 화면에서 말줄임 처리) */
  fileName: string;
  /** 실제로 자동채우기가 되는 서류인지 (백엔드가 hwpx + 필드매핑 기준으로 미리 확인해둔 값) */
  fillable: boolean;
  /** 원본 그대로 받아서 직접 작성할 수 있는 다운로드 URL (채우기 가능 여부와 무관) */
  downloadUrl: string;
}

export interface AnnouncementDetail {
  id: string;
  /** 접수기간 텍스트 (예: "09.01 ~ 09.30 접수") */
  period: string;
  /** D-day 뱃지 문구 (예: "D-6") */
  dday: string;
  /** 공고 제목 */
  title: string;
  /** 해시태그 — 칩이 아니라 한 줄 텍스트로 그대로 렌더한다 */
  hashtags: string;
  /** 지금 로그인한 사용자가 이 공고를 찜했는지 (비로그인이면 항상 false) */
  bookmarked: boolean;
  /** AI 코멘트 박스 본문 */
  aiComment: string;
  /**
   * 사업개요 항목. 항상 4개이고 순서가 고정이다:
   * 0) 소관기관 · 수행기관  1) 지원 대상  2) 신청 방법  3) 문의처
   * MatchingDetail이 이 순서대로 아이콘을 매칭한다.
   */
  overview: OverviewItem[];
  /** 공고 내용 카드 본문 */
  content: string;
  /** 신청서류 목록 */
  docs: RequiredDoc[];
  /** 원 공고 홈페이지 URL (기업마당 pblanc_url) */
  homepageUrl: string | null;
}
