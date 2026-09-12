import DiagnosisReportSummary from "./DiagnosisReportSummary";

const MOCK_CARDS = [
  {
    axis: "타깃 관점",
    title: "원데이 클래스 수강생",
    description: "노트북 작업자 외에, 커피를 배우고 싶은 원데이 클래스 수강생도 잠재 고객으로 넓혀보면 어떨까요.",
  },
  {
    axis: "수익모델 관점",
    title: "구독형 좌석권",
    description: "1회 방문 대신 월 구독형 좌석권을 만들어서, 고정 고객의 재방문 주기를 예측 가능하게 만들어보세요.",
  },
  {
    axis: "보유역량 활용",
    title: "홈카페 키트 판매",
    description: "매장 운영 노하우를 살려서, 원두·도구를 묶은 홈카페 키트를 온라인으로 함께 판매해보는 것도 방법이에요.",
  },
];

/**
 * [개발용 미리보기, 팀 공유용] DiagnosisReportSummary(13-1/14-2 리포트 파트2)를
 * 실제 진단 플로우(로그인 + Q1~Q10 제출)를 거치지 않고 바로 확인하기 위한 목업
 * 래퍼. /dev/report-summary-preview 라우트로만 연결되고, 실제 사용자 흐름에서는
 * 쓰이지 않는다 - DiagnosisStep9.tsx가 제출 성공 후 렌더하는 것과 같은 컴포넌트에
 * 목업 props만 채워서 그대로 보여준다.
 */
function DiagnosisReportSummaryPreview() {
  return (
    <DiagnosisReportSummary
      variant="market"
      target="20~30대 노트북 작업자"
      differentiator="24시간 무인 스터디카페형 좌석 관리"
      revenueModel="시간권 + 월 구독권 혼합"
      coreSkill="바리스타 자격증, 요식업 경력 3년"
      cards={MOCK_CARDS}
    />
  );
}

export default DiagnosisReportSummaryPreview;
