import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useNavigate } from "react-router-dom";
import { getUserEmail, getUserId, logout } from "./auth/session";
import Splash from "./pages/splash/Splash";
import Signup from "./pages/auth/Signup";
import Home from "./pages/home/Home";
import Onboarding from "./pages/onboarding/Onboarding";
import DiagnosisChoice from "./pages/diagnosis/DiagnosisChoice";
import LoginForm from "./components/LoginForm";
import AdminHome from "./pages/admin/AdminHome";
import AdminMembers from "./pages/admin/AdminMembers";
import AnnouncementsSync from "./pages/admin/AnnouncementsSync";
import AdminLayout from "./pages/admin/AdminLayout";
import AdminRoute from "./pages/admin/AdminRoute";
import AdminStyleGuide from "./components/AdminStyleGuide/AdminStyleGuide";
import WebStyleGuide from "./components/WebStyleGuide/WebStyleGuide";
import WebStyleGuideByFeature from "./components/WebStyleGuideByFeature/WebStyleGuideByFeature";
import MatchingList from "./pages/matching/MatchingList";
import MatchingListDraft from "./pages/matching/MatchingListDraft";
import MatchingDetail from "./pages/matching/MatchingDetail";
import DocPreview from "./pages/matching/DocPreview";
import FilterPage from "./pages/matching/FilterPage";
import MyPage from "./pages/mypage/MyPage";
import ProfileEdit from "./pages/mypage/ProfileEdit";
import ProfileEditV2 from "./pages/mypage/ProfileEditV2";
import CustomerSupport from "./pages/support/CustomerSupport";
import CustomerSupportChat from "./pages/support/CustomerSupportChat";
import DiagnosisSelect from "./pages/diagnosis/DiagnosisSelect";
import DiagnosisStep1 from "./pages/diagnosis/DiagnosisStep1";
import DiagnosisStep2 from "./pages/diagnosis/DiagnosisStep2";
import DiagnosisStep3 from "./pages/diagnosis/DiagnosisStep3";
import DiagnosisStep4 from "./pages/diagnosis/DiagnosisStep4";
import DiagnosisStep5 from "./pages/diagnosis/DiagnosisStep5";
import DiagnosisAnswerSummary from "./pages/diagnosis/DiagnosisAnswerSummary";
import DiagnosisIndustryResult from "./pages/diagnosis/DiagnosisIndustryResult";
import DiagnosisReport from "./pages/diagnosis/DiagnosisReport";
// [2026-09-12, 개인 테스트용] 정식 흐름(sessionStorage 의존)과 완전히 분리된 목업
// 사본 - 확인 끝나면 이 2줄 + 아래 라우트 2개 + _test.tsx 파일 2개 지울 것.
import DiagnosisAnswerSummaryTest from "./pages/diagnosis/DiagnosisAnswerSummary_test";
import DiagnosisReportTest from "./pages/diagnosis/DiagnosisReport_test";
// [2026-09-12] 팀원(emkim99-coder) 버전(PSST 확정→업종코드 매칭→상권/기술창업 리포트,
// 별도 화면 3~4개)과 제 버전(세션저장+백그라운드분석+폴링, DiagnosisAnswerSummary/
// DiagnosisReport 2개)이 git stash pop 충돌로 부딪혔었음 - 로직(세션·백그라운드분석·
// 빠른매칭 분기·Q7·Q8 앵커)은 제 버전이 맞고, 겉모습(디자인)만 emkim99님 화면대로
// 다시 입히기로 결정(사용자 확인) - 그래서 메인 흐름은 다시 제 버전
// (DiagnosisAnswerSummary → DiagnosisIndustryResult → DiagnosisReport)으로 복귀,
// emkim99님 화면 4개는 디자인 참고용으로 파일만 남기고 라이브 흐름에서는 안 씀
// (직접 URL 접근 시에만 보임).
// [2026-09-12] DiagnosisIndustryResult는 emkim99님 DiagnosisIndustryCode.tsx(라디오
// 선택형)와 달리, 이미 확정된 매칭 결과(sessionStorage)를 그대로 보여주기만 하는
// 순수 표시 화면 - 상세 이유는 DiagnosisIndustryResult.tsx 자체 주석 참고.
import DiagnosisPsstConfirm from "./pages/diagnosis/DiagnosisPsstConfirm";
// [2026-09-12, 개인 테스트용] 위 두 test 파일과 동일한 이유/패턴 - 확인 끝나면
// 이 줄 + 아래 라우트 1개 + _test.tsx 파일 1개 지울 것.
import DiagnosisPsstConfirmTest from "./pages/diagnosis/DiagnosisPsstConfirm_test";
import DiagnosisIndustryCode from "./pages/diagnosis/DiagnosisIndustryCode";
// [2026-09-12, 개인 테스트용] 위 psst-confirm-test와 동일한 이유/패턴 - 확인 끝나면
// 이 줄 + 아래 라우트 1개 + _test.tsx 파일 1개 지울 것.
import DiagnosisIndustryCodeTest from "./pages/diagnosis/DiagnosisIndustryCode_test";
import DiagnosisStep6 from "./pages/diagnosis/DiagnosisStep6";
import DiagnosisMarketReport from "./pages/diagnosis/DiagnosisMarketReport";
import DiagnosisTechReport from "./pages/diagnosis/DiagnosisTechReport";
// [2026-09-12, 개인 테스트용] 위 psst-confirm-test와 동일한 이유/패턴 - 확인 끝나면
// 이 2줄 + 아래 라우트 2개 + _test.tsx 파일 2개 지울 것.
import DiagnosisMarketReportTest from "./pages/diagnosis/DiagnosisMarketReport_test";
import DiagnosisTechReportTest from "./pages/diagnosis/DiagnosisTechReport_test";
import DiagnosisStep7 from "./pages/diagnosis/DiagnosisStep7";
import DiagnosisStep8 from "./pages/diagnosis/DiagnosisStep8";
import DiagnosisStep9 from "./pages/diagnosis/DiagnosisStep9";
import DiagnosisReportSummaryPreview from "./pages/diagnosis/DiagnosisReportSummaryPreview";
// [2026-09-13, 개인 디자인 확인용] 진단 흐름 화면들이 전부 이전 단계 가드가 있어서
// 직접 URL로 들어가면 앞 단계로 튕겨버려 디자인만 따로 확인하기 어렵다는 요청으로
// 만든 격리 사본들 - 세션/백엔드 의존 전혀 없음. 확인 끝나면 이 블록 + 아래 라우트들
// + _test.tsx 파일들 지울 것. (DiagnosisStep4는 같은 이름의 무관한 기존 스크래치
// 파일이 이미 있어서 이번 배치에서 제외 - App.tsx 하단 라우트 주석 참고)
import DiagnosisSelectTest from "./pages/diagnosis/DiagnosisSelect_test";
import DiagnosisStep2Test from "./pages/diagnosis/DiagnosisStep2_test";
import DiagnosisStep3Test from "./pages/diagnosis/DiagnosisStep3_test";
import DiagnosisStep5Test from "./pages/diagnosis/DiagnosisStep5_test";
import DiagnosisStep6Test from "./pages/diagnosis/DiagnosisStep6_test";
import DiagnosisStep7Test from "./pages/diagnosis/DiagnosisStep7_test";
import DiagnosisStep8Test from "./pages/diagnosis/DiagnosisStep8_test";
import DiagnosisStep9Test from "./pages/diagnosis/DiagnosisStep9_test";
import DiagnosisIndustryResultTest from "./pages/diagnosis/DiagnosisIndustryResult_test";
// [2026-09-13, 디자인 검토용, 라이브 미적용] "업종코드를 찾았어요" 화면을 프로토타입
// 실측값대로 다시 만든 미리보기 - 검토 후 괜찮으면 DiagnosisIndustryResult.tsx에
// 반영하고 이 줄+아래 라우트+파일 정리할 것. 상세 이유는 파일 자체 주석 참고.
import DiagnosisIndustryResultPreview from "./pages/diagnosis/DiagnosisIndustryResultPreview";

/**
 * [임시/디버그] 지금 로그인된 사람이 누구인지 확인용 - 확인 끝나면 지울 것.
 * 화면 가리지 않게 우하단 작은 플로팅 점으로 표시, 클릭하면 펼쳐서 상세 표시.
 * [2026-09-12, 사용자 확인] 펼쳤을 때 로그아웃 버튼도 같이 노출 - MyPage.tsx의
 * 로그아웃(clearSession + /login 이동)과 동일하게 동작.
 */
function DevAuthBadge() {
  const navigate = useNavigate();
  const [session, setSessionState] = useState({ userId: getUserId(), email: getUserEmail() });
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const tick = () => setSessionState({ userId: getUserId(), email: getUserEmail() });
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  const color = session.userId ? "#0a7d32" : "#c0392b";

  const handleLogout = async () => {
    await logout();
    setSessionState({ userId: getUserId(), email: getUserEmail() });
    navigate("/login");
  };

  return (
    <div
      style={{
        position: "fixed",
        bottom: 12,
        right: 12,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        gap: 6,
        borderRadius: 999,
        padding: expanded ? "5px 8px 5px 10px" : 0,
        background: expanded ? "#222" : "transparent",
        boxShadow: expanded ? "0 1px 4px rgba(0,0,0,0.3)" : "none",
      }}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          border: "none",
          borderRadius: 999,
          padding: 0,
          width: expanded ? "auto" : 14,
          height: expanded ? "auto" : 14,
          background: expanded ? "transparent" : color,
          color: "#fff",
          fontSize: 11,
          lineHeight: 1.4,
          cursor: "pointer",
          boxShadow: expanded ? "none" : "0 1px 4px rgba(0,0,0,0.3)",
        }}
        title="[DEV] 로그인 상태 (클릭해서 펼치기)"
      >
        {expanded ? (
          <>
            <span style={{ width: 8, height: 8, borderRadius: 999, background: color, flexShrink: 0 }} />
            {session.userId
              ? `user_id=${session.userId}${session.email ? ` (${session.email})` : ""}`
              : "로그인 안 됨"}
          </>
        ) : null}
      </button>
      {expanded && session.userId && (
        <button
          type="button"
          onClick={handleLogout}
          style={{
            border: "none",
            borderRadius: 999,
            padding: "3px 8px",
            background: "#c0392b",
            color: "#fff",
            fontSize: 11,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          로그아웃
        </button>
      )}
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <DevAuthBadge />
      <Routes>
        <Route path="/" element={<Splash />} />
        <Route path="/home" element={<Home />} />
        <Route path="/login" element={<LoginForm variant="user" />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/diagnosis/choice" element={<DiagnosisChoice />} />
        <Route path="/matching" element={<MatchingList />} />
        {/* [2026-09-12] 디자인 검토 완료 - 실제 /matching(MatchingList.tsx)에 반영됨.
            이 사본 자체는 팀원 참고용으로 당분간 남겨둠. */}
        <Route path="/matching-draft" element={<MatchingListDraft />} />
        <Route path="/matching/filter" element={<FilterPage />} />
        <Route path="/matching/:id" element={<MatchingDetail />} />
        <Route path="/matching/:id/doc-preview" element={<DocPreview />} />
        <Route path="/mypage" element={<MyPage />} />
        <Route path="/mypage/edit" element={<ProfileEdit />} />
        <Route path="/edit-v2" element={<ProfileEditV2 />} />
        <Route path="/support" element={<CustomerSupport />} />
        <Route path="/support/chat" element={<CustomerSupportChat />} />
        <Route path="/diagnosis/select" element={<DiagnosisSelect />} />
        <Route path="/diagnosis/1" element={<DiagnosisStep1 />} />
        <Route path="/diagnosis/3" element={<DiagnosisStep2 />} />
        <Route path="/diagnosis/4" element={<DiagnosisStep3 />} />
        <Route path="/diagnosis/5" element={<DiagnosisStep4 />} />
        <Route path="/diagnosis/6" element={<DiagnosisStep5 />} />
        {/* [2026-09-12] 메인 흐름 - DiagnosisStep5.tsx가 Q6 제출 후 여기로 이동시킨다
            (위 import 주석 참고). emkim99님 화면 디자인을 이쪽으로 옮겨 입히는 작업 진행 중. */}
        <Route path="/diagnosis/summary" element={<DiagnosisAnswerSummary />} />
        <Route path="/diagnosis/industry-result" element={<DiagnosisIndustryResult />} />
        <Route path="/diagnosis/report" element={<DiagnosisReport />} />
        {/* [2026-09-13] 마이페이지 "분석 리포트"에서 지난 세션을 다시 열어볼 때 - 같은
            컴포넌트가 URL의 sessionId 유무로 "진행 중" vs "완료된 리포트 보기"를 가른다. */}
        <Route path="/diagnosis/report/:sessionId" element={<DiagnosisReport />} />
        {/* [2026-09-12, 개인 테스트용] 확인 끝나면 이 2줄도 위 import 2줄과 같이 지울 것 */}
        <Route path="/diagnosis/summary-test" element={<DiagnosisAnswerSummaryTest />} />
        <Route path="/diagnosis/report-test" element={<DiagnosisReportTest />} />
        {/* [2026-09-12] emkim99님 버전 화면 - 디자인 참고용, 라이브 흐름에서는 안 씀
            (위 import 주석 참고). 직접 URL 접근 시에만 보임. */}
        <Route path="/diagnosis/psst-confirm" element={<DiagnosisPsstConfirm />} />
        {/* [2026-09-12, 개인 테스트용] 확인 끝나면 이 줄도 위 import와 같이 지울 것 */}
        <Route path="/diagnosis/psst-confirm-test" element={<DiagnosisPsstConfirmTest />} />
        <Route path="/diagnosis/industry-code" element={<DiagnosisIndustryCode />} />
        {/* [2026-09-12, 개인 테스트용] 확인 끝나면 이 줄도 위 import와 같이 지울 것 */}
        <Route path="/diagnosis/industry-code-test" element={<DiagnosisIndustryCodeTest />} />
        <Route path="/diagnosis/market-report" element={<DiagnosisMarketReport />} />
        <Route path="/diagnosis/tech-report" element={<DiagnosisTechReport />} />
        {/* [2026-09-12, 개인 테스트용] 확인 끝나면 이 2줄도 위 import 2줄과 같이 지울 것 */}
        <Route path="/diagnosis/market-report-test" element={<DiagnosisMarketReportTest />} />
        <Route path="/diagnosis/tech-report-test" element={<DiagnosisTechReportTest />} />
        <Route path="/diagnosis/7" element={<DiagnosisStep6 />} />
        <Route path="/diagnosis/8" element={<DiagnosisStep7 />} />
        <Route path="/diagnosis/9" element={<DiagnosisStep8 />} />
        <Route path="/diagnosis/10" element={<DiagnosisStep9 />} />
        {/* [2026-09-13, 개인 디자인 확인용] 확인 끝나면 이 라우트들도 위 import 블록과
            같이 지울 것. DiagnosisStep4는 같은 이름의 무관한 기존 스크래치 파일이 있어
            이번 배치에서 제외했음(App.tsx 위쪽 import 주석 참고) - Q5(매장 운영 형태)
            디자인 확인이 필요하면 별도 파일명으로 요청할 것. */}
        <Route path="/diagnosis/select-test" element={<DiagnosisSelectTest />} />
        <Route path="/diagnosis/3-test" element={<DiagnosisStep2Test />} />
        <Route path="/diagnosis/4-test" element={<DiagnosisStep3Test />} />
        <Route path="/diagnosis/6-test" element={<DiagnosisStep5Test />} />
        <Route path="/diagnosis/7-test" element={<DiagnosisStep6Test />} />
        <Route path="/diagnosis/8-test" element={<DiagnosisStep7Test />} />
        <Route path="/diagnosis/9-test" element={<DiagnosisStep8Test />} />
        <Route path="/diagnosis/10-test" element={<DiagnosisStep9Test />} />
        <Route path="/diagnosis/industry-result-test" element={<DiagnosisIndustryResultTest />} />
        <Route path="/diagnosis/industry-result-preview" element={<DiagnosisIndustryResultPreview />} />
        <Route path="/style-guide" element={<AdminStyleGuide />} />
        <Route path="/dev/web-style-guide" element={<WebStyleGuide />} />
        <Route path="/dev/web-style-guide-by-feature" element={<WebStyleGuideByFeature />} />
        <Route path="/dev/report-summary-preview" element={<DiagnosisReportSummaryPreview />} />
        <Route path="/admin/login" element={<LoginForm variant="admin" />} />
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminLayout />
            </AdminRoute>
          }
        >
          <Route index element={<AdminHome />} />
          <Route path="members" element={<AdminMembers />} />
          {/* [임시] raw -> announcements 통합 반영 실행/모니터 */}
          <Route path="announcements-sync" element={<AnnouncementsSync />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
