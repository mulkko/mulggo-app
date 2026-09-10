/**
 * 공고 상세(지원사업 상세) 화면 더미데이터.
 *
 * 공고 리스트(MatchingList.tsx)의 카드 5개와 같은 id(a1~a5)를 키로 갖는다.
 * 리스트에서 카드를 누르면 `/matching/:id`로 이동하고, 상세 화면(MatchingDetail.tsx)은
 * 이 맵에서 해당 id의 레코드를 찾아 렌더한다.
 * 백엔드 공고 상세 API가 붙으면 이 맵을 응답 데이터로 교체한다.
 *
 * 값 출처: 프로토타입 "지원사업 상세"(is.detail) 화면.
 * a1을 프로토타입 기준으로 채우고, a2~a5는 리스트 카드 정보에 맞춰 변형한 더미값이다.
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
  /** AI 코멘트 박스 본문 (더미 문구) */
  aiComment: string;
  /**
   * 사업개요 항목. 항상 4개이고 순서가 고정이다:
   * 0) 소관기관 · 수행기관  1) 지원 대상  2) 신청 방법  3) 문의처
   * MatchingDetail이 이 순서대로 아이콘을 매칭한다.
   */
  overview: OverviewItem[];
  /** 공고 내용 카드 본문 (더미 문구) */
  content: string;
  /** 신청서류 목록 */
  docs: RequiredDoc[];
  /** 원 공고 홈페이지 URL — 아직 더미 단계라 전부 null */
  homepageUrl: string | null;
}

/** a1 기준 신청서류 (여러 공고에서 재사용) */
const SAMPLE_DOCS: RequiredDoc[] = [
  { attachmentId: 0, fileName: "2026년 청년 소상공인 창업자금 공고문.pdf", fillable: false, downloadUrl: "" },
  { attachmentId: 0, fileName: "신청서 양식.hwp", fillable: false, downloadUrl: "" },
];

export const DUMMY_ANNOUNCEMENT_DETAILS: Record<string, AnnouncementDetail> = {
  a1: {
    id: "a1",
    period: "09.01 ~ 09.30 접수",
    dday: "D-6",
    title: "2026년 청년 소상공인 창업 자금 지원",
    hashtags: "#내수 #국내일반인력 #청년창업 #소상공인 #창업자금 #저금리대출",
    bookmarked: false,
    aiComment:
      "지역가산(마포구), 청년가산(만 39세 이하), 업종가산(외식·카페) 조건이 회원님 상황에 적합해요. 창업자금 최대 7,000만원(연 1.5% 고정금리)으로 초기 시설투자비 부담을 낮추는 자금 조건이에요.",
    overview: [
      { label: "소관기관 · 수행기관", value: "중소벤처기업부 · 중소기업진흥공단" },
      { label: "지원 대상", value: "만 39세 이하 예비창업자 및 창업 3년 이내 소상공인" },
      { label: "신청 방법", value: "중소기업진흥공단 온라인 접수 → 서류심사 → 대면평가" },
      { label: "문의처", value: "중소기업 통합콜센터 1357" },
    ],
    content:
      "코로나19 이후 위축된 청년 창업 생태계를 활성화하기 위해 유망한 기술과 창의적 아이디어를 가진 청년 소상공인들의 초기 사업화를 적극 지원합니다. 안정적인 비즈니스 궤도 진입 및 청년 일자리 창출 극대화를 위해 운영 자금이 적극 지원됩니다.",
    docs: SAMPLE_DOCS,
    homepageUrl: null,
  },
  a2: {
    id: "a2",
    period: "09.10 ~ 09.28 접수",
    dday: "D-3",
    title: "여성 창업 아이디어 경진대회",
    hashtags: "#여성창업 #경진대회 #예비창업 #사업화지원 #멘토링",
    bookmarked: false,
    aiComment:
      "여성 예비창업자 우대 트랙이 회원님 프로필과 맞아요. 수상 시 사업화 자금과 6개월 멘토링이 연계되어, 아이디어 검증 단계에 있는 지금 활용도가 높아요.",
    overview: [
      { label: "소관기관 · 수행기관", value: "중소벤처기업부 · 여성기업종합지원센터" },
      { label: "지원 대상", value: "여성 예비창업자 및 창업 2년 이내 여성기업 대표" },
      { label: "신청 방법", value: "여성기업종합지원센터 온라인 접수 → 1차 서류 → 발표 심사" },
      { label: "문의처", value: "여성기업종합지원센터 창업지원팀 02-1234-5678" },
    ],
    content:
      "혁신적인 아이디어를 가진 여성 창업가를 발굴하고 사업화를 지원하기 위한 경진대회입니다. 본선 진출 팀에는 시제품 제작비와 전문 멘토링이 제공되며, 최종 수상 팀은 후속 창업지원사업 연계 시 가점을 받습니다.",
    docs: [
      { attachmentId: 0, fileName: "여성 창업 아이디어 경진대회 모집공고.pdf", fillable: false, downloadUrl: "" },
      { attachmentId: 0, fileName: "참가 신청서 및 사업계획서 양식.hwp", fillable: false, downloadUrl: "" },
    ],
    homepageUrl: null,
  },
  a3: {
    id: "a3",
    period: "09.05 ~ 10.15 접수",
    dday: "D-18",
    title: "마포구 골목상권 특화 창업 지원사업",
    hashtags: "#골목상권 #지역특화 #마포구 #점포임차 #인테리어지원",
    bookmarked: false,
    aiComment:
      "사업장이 마포구에 있어 지역 요건을 충족해요. 점포 임차료와 인테리어 비용을 함께 지원해, 오프라인 매장 오픈을 준비 중인 회원님께 부담이 큰 초기 고정비를 낮출 수 있어요.",
    overview: [
      { label: "소관기관 · 수행기관", value: "마포구청 · 마포구 소상공인지원센터" },
      { label: "지원 대상", value: "마포구 내 창업 예정이거나 창업 1년 이내인 소상공인" },
      { label: "신청 방법", value: "마포구청 일자리경제과 방문 접수 또는 이메일 접수" },
      { label: "문의처", value: "마포구청 일자리경제과 02-3153-8000" },
    ],
    content:
      "지역 골목상권의 활력을 높이고 특색 있는 점포를 육성하기 위해 마포구가 자체 재원으로 추진하는 창업 지원사업입니다. 점포 임차료, 간판·인테리어 개선비, 홍보물 제작비 등을 항목별 한도 내에서 지원합니다.",
    docs: [
      { attachmentId: 0, fileName: "마포구 골목상권 특화 창업 지원사업 공고문.pdf", fillable: false, downloadUrl: "" },
      { attachmentId: 0, fileName: "지원 신청서 양식.hwp", fillable: false, downloadUrl: "" },
    ],
    homepageUrl: null,
  },
  a4: {
    id: "a4",
    period: "08.20 ~ 10.31 접수",
    dday: "D-32",
    title: "외식업 스마트 매장 전환 지원",
    hashtags: "#외식업 #스마트매장 #키오스크 #테이블오더 #디지털전환",
    bookmarked: false,
    aiComment:
      "외식업 업종 요건에 해당해요. 키오스크·테이블오더·주방 자동화 설비 도입 비용의 일부를 지원해, 인건비 부담을 줄이고 회전율을 높이려는 회원님 매장에 맞는 사업이에요.",
    overview: [
      { label: "소관기관 · 수행기관", value: "중소벤처기업부 · 소상공인시장진흥공단" },
      { label: "지원 대상", value: "사업자등록을 마친 외식업(음식점업) 영위 소상공인" },
      { label: "신청 방법", value: "소상공인시장진흥공단 온라인 신청 → 현장 확인 → 협약" },
      { label: "문의처", value: "소상공인 통합콜센터 1357" },
    ],
    content:
      "외식업 소상공인의 디지털 전환을 돕기 위해 스마트 주문·결제 시스템과 주방 자동화 설비 도입 비용을 지원합니다. 도입 설비의 종류에 따라 지원 한도가 다르며, 자부담률은 총 사업비의 30%입니다.",
    docs: [
      { attachmentId: 0, fileName: "외식업 스마트 매장 전환 지원 공고문.pdf", fillable: false, downloadUrl: "" },
      { attachmentId: 0, fileName: "사업 신청서 양식.hwp", fillable: false, downloadUrl: "" },
    ],
    homepageUrl: null,
  },
  a5: {
    id: "a5",
    period: "09.01 ~ 11.30 접수",
    dday: "D-45",
    title: "2026년 전 업종 소상공인 디지털 전환 지원",
    hashtags: "#디지털전환 #전업종 #온라인판로 #스마트기기 #교육연계",
    bookmarked: false,
    aiComment:
      "업종 제한이 없어 회원님도 신청 대상이에요. 온라인 판로 개척, 스마트 기기 도입, 디지털 교육을 묶어 지원하므로, 온라인 채널을 이제 막 시작하는 단계라면 활용도가 높아요.",
    overview: [
      { label: "소관기관 · 수행기관", value: "중소벤처기업부 · 소상공인시장진흥공단" },
      { label: "지원 대상", value: "전 업종 소상공인 (일부 사행성·유흥 업종 제외)" },
      { label: "신청 방법", value: "소상공인 지원포털 온라인 접수 → 요건 검토 → 선정" },
      { label: "문의처", value: "소상공인 통합콜센터 1357" },
    ],
    content:
      "소상공인의 디지털 역량 강화를 위해 온라인 판로 진출, 스마트 결제·재고관리 기기 도입, 디지털 마케팅 교육을 패키지로 지원합니다. 신청자는 3개 세부 프로그램 중 필요한 항목을 선택해 신청할 수 있습니다.",
    docs: [
      { attachmentId: 0, fileName: "2026년 소상공인 디지털 전환 지원 통합공고.pdf", fillable: false, downloadUrl: "" },
      { attachmentId: 0, fileName: "참여 신청서 양식.hwp", fillable: false, downloadUrl: "" },
    ],
    homepageUrl: null,
  },
};

/** id로 공고 상세 더미데이터를 찾는다. 없으면 undefined. */
export function getAnnouncementDetail(id: string | undefined): AnnouncementDetail | undefined {
  if (!id) return undefined;
  return DUMMY_ANNOUNCEMENT_DETAILS[id];
}
