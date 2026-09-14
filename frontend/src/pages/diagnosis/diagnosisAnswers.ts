// 사업구체화 진단(슬롯필링) 5개 화면(진단방식선택 + 구체화 진단1~4)이 공유하는
// 답변 저장소. 화면마다 라우트가 분리돼 있어서(dev_links.html 목업 구조 기준) 답변을
// sessionStorage에 쌓아두고 마지막 화면(구체화 진단4)에서 한 번에 제출한다. 탭 닫으면
// 초기화되는 정도면 충분 - 로그인 세션처럼 오래 유지할 필요 없음.
//
// [2026-09-10] 업종코드(KSIC) 매칭은 팀에서 별도로 다시 만들고 있어서(사용자 확인),
// 이 5개 화면은 질문 수집 + 제출까지만 한다. 제출 API(POST /api/test/slot-filling)가
// 내려주는 ksic/report_type은 화면에서 그냥 안 씀 - 나중에 업종분류 쪽이 완성되면
// 결과 화면(DiagnosisStep4)에서 마저 연결하면 됨.
//
// 근거 문서: E:\3차프로젝트\슬롯필링_기능_설계_260905.pdf, 슬롯필링_260909.xlsx.
// 질문 문구/흐름은 이미 검증된 frontend/dev/idea-flow-test.html과 동일하게 맞춤.

export type Origin = "problem" | "opportunity";

// ①고객방문형 오프라인 매장·공간 / ②예약 방문형 서비스 공간 / ③배달·제조 중심 고객방문없음 /
// ④온라인 판매·중개 플랫폼 / ⑤앱·소프트웨어·디지털 서비스
export type StoreType = "offline" | "booking" | "delivery" | "online" | "digital";

export type DiagnosisMode = "fast" | "precise";

export interface DiagnosisAnswers {
  // [2026-09-11] DiagnosisChoice(/diagnosis/choice)에서 고른 트랙 - "빠른 진단"은
  // 필수 6문항+정리+리포트 후 바로 공고매칭리스트로, "정밀 진단"은 거기서 선택
  // 4문항(Q7~Q10)까지 이어서 진행한다(사용자 확인).
  mode?: DiagnosisMode;
  origin?: Origin;
  seedInterest?: string;
  problemToSolve?: string;
  solutionApproach?: string;
  hasStore?: boolean;
  storeType?: StoreType;
  // [2026-09-11] 6번(지역) 제출 시 POST /api/diagnosis/start로 세션이 만들어지면서
  // 받는 id. 10번(마지막) 제출이 이 id로 같은 세션에 이어붙인다(backend/api/diagnosis.py
  // 상단 주석 참고).
  sessionId?: number;
  resolvedKsicCodes?: string[];
  // /start 응답의 업종코드 판정 요약 - 분석 리포트 화면(DiagnosisReport) 상단에 보여준다.
  industryMatchName?: string;
  industryMatchState?: string;
  industryMatchConfidence?: string;
  // [2026-09-14] 후보(최대 3개) 코드별 업종명 - code -> name. industryMatchName은
  // 1순위 이름만 담아서, 업종코드 결과/분석 리포트 셀렉박스가 후보 3개 전부에 같은
  // 이름을 보여주던 버그가 있었음(사용자 확인) - 이제 코드마다 자기 이름을 찾아 쓴다.
  industryMatchCodeNames?: Record<string, string>;
  // /start 응답으로 같이 받는 앵커 문구(있으면 7·8번 화면 하드코딩 문구 대신 사용) -
  // 매장형태로 카페형/기술창업형이 갈려 내용 출처가 다르지만 프론트는 그냥 문자열로 받아 쓴다.
  targetAnchor?: string;
  differentiatorAnchor?: string;
  // /start 응답의 원본 리포트 - 지역 제출 직후 "분석 리포트" 화면(DiagnosisReport)이
  // track에 따라 marketAnalysis 또는 techAnalysis 하나만 그려서 보여준다.
  track?: "cafe" | "tech";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  marketAnalysis?: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  techAnalysis?: any;
  // [2026-09-13] 업종코드 후보(최대 3개) 전부를 각자 분석한 결과 - 코드 -> {marketAnalysis,
  // techAnalysis} 맵. 분석 리포트 화면(DiagnosisReport) 상단 셀렉박스가 이걸로 후보를
  // 전환해가며 보여준다. marketAnalysis/techAnalysis(위 두 필드)는 그중 1순위(후보
  // 배열의 첫 코드) 결과와 항상 같다(하위호환 - Q7·Q8 앵커는 계속 1순위 기준).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  analysisByCode?: Record<string, { marketAnalysis?: any; techAnalysis?: any; failed?: boolean }>;
  sido?: string;
  sigungu?: string;
  dong?: string;
  target?: string;
  differentiator?: string;
  revenueModel?: string;
  coreSkill?: string;
  ksicCode?: string;
  ksicName?: string;
}

const STORAGE_KEY = "mulkko_diagnosis_answers";

export function getDiagnosisAnswers(): DiagnosisAnswers {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DiagnosisAnswers) : {};
  } catch {
    return {};
  }
}

export function saveDiagnosisAnswers(patch: Partial<DiagnosisAnswers>): DiagnosisAnswers {
  const next = { ...getDiagnosisAnswers(), ...patch };
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // 프라이빗 모드 등 sessionStorage 못 쓰는 환경 - 이번 진단 이어가기만 안 될 뿐 치명적이지 않음
  }
  return next;
}

export function clearDiagnosisAnswers(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

// 11(PSST 확정)에서 Q1~Q6 카드를 눌러 해당 진단 화면으로 돌아갔을 때, 그 화면에서
// 수정을 마치고 원래 하던 다음 화면(Q7 등) 대신 다시 11로 돌아오게 하는 용도.
// Step1~5/Select의 제출 핸들러가 이 값이 있으면 그리로, 없으면 평소 다음 화면으로 이동한다.
const RETURN_TO_KEY = "mulkko_diagnosis_return_to";

export function setDiagnosisReturnTo(path: string): void {
  try {
    sessionStorage.setItem(RETURN_TO_KEY, path);
  } catch {
    // ignore
  }
}

export function consumeDiagnosisReturnTo(): string | null {
  try {
    const path = sessionStorage.getItem(RETURN_TO_KEY);
    if (path) sessionStorage.removeItem(RETURN_TO_KEY);
    return path;
  } catch {
    return null;
  }
}

// 슬롯필링_260909.xlsx 시트 2개(문제해결형/기회추구형) 기준 - 저장 구조·데이터 처리는
// 완전히 동일하고 화면 표시 문구만 갈린다(PDF 4장). idea-flow-test.html과 동일 문구.
export const DIAGNOSIS_QUESTIONS: Record<
  Origin,
  { problemToSolve: string; solutionApproach: string }
> = {
  problem: {
    problemToSolve: "고객이 겪고 있는 문제는 구체적으로 무엇인가요?",
    solutionApproach: "이 문제를 어떤 제품이나 서비스로 해결하실 건가요?",
  },
  opportunity: {
    problemToSolve: "시장에 아직 없어서 아쉬운 점은 무엇인가요?",
    solutionApproach: "이 아이디어를 어떤 제품이나 서비스로 구현하실 건가요?",
  },
};

export const MIN_ANSWER_LENGTH = 10;
