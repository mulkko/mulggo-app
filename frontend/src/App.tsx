import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ensureDevAutoLogin, getUserEmail, getUserId } from "./auth/session";
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
import MatchingList from "./pages/matching/MatchingList";
import MatchingListDraft from "./pages/matching/MatchingListDraft";
import MatchingDetail from "./pages/matching/MatchingDetail";
import DocPreview from "./pages/matching/DocPreview";
import FilterPage from "./pages/matching/FilterPage";
import MyPage from "./pages/mypage/MyPage";
import ProfileEdit from "./pages/mypage/ProfileEdit";
import CustomerSupport from "./pages/support/CustomerSupport";
import CustomerSupportChat from "./pages/support/CustomerSupportChat";
import DiagnosisSelect from "./pages/diagnosis/DiagnosisSelect";
import DiagnosisStep1 from "./pages/diagnosis/DiagnosisStep1";
import DiagnosisStep2 from "./pages/diagnosis/DiagnosisStep2";
import DiagnosisStep3 from "./pages/diagnosis/DiagnosisStep3";
import DiagnosisStep4 from "./pages/diagnosis/DiagnosisStep4";
import DiagnosisStep5 from "./pages/diagnosis/DiagnosisStep5";
import DiagnosisPsstConfirm from "./pages/diagnosis/DiagnosisPsstConfirm";
import DiagnosisIndustryCode from "./pages/diagnosis/DiagnosisIndustryCode";
import DiagnosisStep6 from "./pages/diagnosis/DiagnosisStep6";
import DiagnosisMarketReport from "./pages/diagnosis/DiagnosisMarketReport";
import DiagnosisTechReport from "./pages/diagnosis/DiagnosisTechReport";
import DiagnosisStep7 from "./pages/diagnosis/DiagnosisStep7";
import DiagnosisStep8 from "./pages/diagnosis/DiagnosisStep8";
import DiagnosisStep9 from "./pages/diagnosis/DiagnosisStep9";
import DiagnosisReportSummaryPreview from "./pages/diagnosis/DiagnosisReportSummaryPreview";

/**
 * [임시/디버그] 지금 로그인된 사람이 누구인지 확인용 - 확인 끝나면 지울 것.
 * 화면 가리지 않게 우하단 작은 플로팅 점으로 표시, 클릭하면 펼쳐서 상세 표시.
 */
function DevAuthBadge() {
  const [session, setSessionState] = useState({ userId: getUserId(), email: getUserEmail() });
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const tick = () => setSessionState({ userId: getUserId(), email: getUserEmail() });
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  const color = session.userId ? "#0a7d32" : "#c0392b";

  return (
    <button
      type="button"
      onClick={() => setExpanded((v) => !v)}
      style={{
        position: "fixed",
        bottom: 12,
        right: 12,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        gap: 6,
        border: "none",
        borderRadius: 999,
        padding: expanded ? "5px 10px" : 0,
        width: expanded ? "auto" : 14,
        height: expanded ? "auto" : 14,
        background: expanded ? "#222" : color,
        color: "#fff",
        fontSize: 11,
        lineHeight: 1.4,
        cursor: "pointer",
        boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
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
  );
}

function App() {
  useEffect(() => {
    ensureDevAutoLogin();
  }, []);

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
        {/* [DRAFT] 업종맞춤/업종무관 2그룹 분리 검토용 - MatchingList.tsx 원본은 그대로 둔 사본 */}
        <Route path="/matching-draft" element={<MatchingListDraft />} />
        <Route path="/matching/filter" element={<FilterPage />} />
        <Route path="/matching/:id" element={<MatchingDetail />} />
        <Route path="/matching/:id/doc-preview" element={<DocPreview />} />
        <Route path="/mypage" element={<MyPage />} />
        <Route path="/mypage/edit" element={<ProfileEdit />} />
        <Route path="/support" element={<CustomerSupport />} />
        <Route path="/support/chat" element={<CustomerSupportChat />} />
        <Route path="/diagnosis/select" element={<DiagnosisSelect />} />
        <Route path="/diagnosis/1" element={<DiagnosisStep1 />} />
        <Route path="/diagnosis/3" element={<DiagnosisStep2 />} />
        <Route path="/diagnosis/4" element={<DiagnosisStep3 />} />
        <Route path="/diagnosis/5" element={<DiagnosisStep4 />} />
        <Route path="/diagnosis/6" element={<DiagnosisStep5 />} />
        <Route path="/diagnosis/psst-confirm" element={<DiagnosisPsstConfirm />} />
        <Route path="/diagnosis/industry-code" element={<DiagnosisIndustryCode />} />
        <Route path="/diagnosis/market-report" element={<DiagnosisMarketReport />} />
        <Route path="/diagnosis/tech-report" element={<DiagnosisTechReport />} />
        <Route path="/diagnosis/7" element={<DiagnosisStep6 />} />
        <Route path="/diagnosis/8" element={<DiagnosisStep7 />} />
        <Route path="/diagnosis/9" element={<DiagnosisStep8 />} />
        <Route path="/diagnosis/10" element={<DiagnosisStep9 />} />
        <Route path="/style-guide" element={<AdminStyleGuide />} />
        <Route path="/dev/web-style-guide" element={<WebStyleGuide />} />
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
