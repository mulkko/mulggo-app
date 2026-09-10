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

export interface DiagnosisAnswers {
  origin?: Origin;
  seedInterest?: string;
  problemToSolve?: string;
  solutionApproach?: string;
  hasStore?: boolean;
  sido?: string;
  sigungu?: string;
  dong?: string;
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
