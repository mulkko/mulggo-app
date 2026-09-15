import { BrowserRouter, Route, Routes } from "react-router-dom";
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
import RequireAuth from "./components/RequireAuth/RequireAuth";
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
import DiagnosisAnswerSummaryTest from "./pages/diagnosis/_backup/DiagnosisAnswerSummary_test";
import DiagnosisReportTest from "./pages/diagnosis/_backup/DiagnosisReport_test";
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
import DiagnosisPsstConfirm from "./pages/diagnosis/_backup/DiagnosisPsstConfirm";
// [2026-09-12, 개인 테스트용] 위 두 test 파일과 동일한 이유/패턴 - 확인 끝나면
// 이 줄 + 아래 라우트 1개 + _test.tsx 파일 1개 지울 것.
import DiagnosisPsstConfirmTest from "./pages/diagnosis/_backup/DiagnosisPsstConfirm_test";
import DiagnosisIndustryCode from "./pages/diagnosis/_backup/DiagnosisIndustryCode";
// [2026-09-12, 개인 테스트용] 위 psst-confirm-test와 동일한 이유/패턴 - 확인 끝나면
// 이 줄 + 아래 라우트 1개 + _test.tsx 파일 1개 지울 것.
import DiagnosisIndustryCodeTest from "./pages/diagnosis/_backup/DiagnosisIndustryCode_test";
import DiagnosisStep6 from "./pages/diagnosis/DiagnosisStep6";
import DiagnosisMarketReport from "./pages/diagnosis/_backup/DiagnosisMarketReport";
import DiagnosisTechReport from "./pages/diagnosis/_backup/DiagnosisTechReport";
// [2026-09-12, 개인 테스트용] 위 psst-confirm-test와 동일한 이유/패턴 - 확인 끝나면
// 이 2줄 + 아래 라우트 2개 + _test.tsx 파일 2개 지울 것.
import DiagnosisMarketReportTest from "./pages/diagnosis/_backup/DiagnosisMarketReport_test";
import DiagnosisTechReportTest from "./pages/diagnosis/_backup/DiagnosisTechReport_test";
import DiagnosisStep7 from "./pages/diagnosis/DiagnosisStep7";
import DiagnosisStep8 from "./pages/diagnosis/DiagnosisStep8";
import DiagnosisStep9 from "./pages/diagnosis/DiagnosisStep9";
import DiagnosisReportSummaryPreview from "./pages/diagnosis/_backup/DiagnosisReportSummaryPreview";
// [2026-09-13, 개인 확인용] report-summary-preview의 헤더/서브헤더/하단버튼 구조는
// 그대로 두고, 스크롤 콘텐츠 영역 안쪽 내용만 비웠다 + 하단에 실제 BottomNav 추가.
// 확인 끝나면 이 줄 + 아래 라우트 + 파일 지울 것.
import DiagnosisReportSummaryFixedLayoutTest from "./pages/diagnosis/DiagnosisReportSummaryFixedLayout_test";
import OcrPopupPreview from "./pages/onboarding/OcrPopupPreview";
// [2026-09-13, 개인 디자인 확인용] 진단 흐름 화면들이 전부 이전 단계 가드가 있어서
// 직접 URL로 들어가면 앞 단계로 튕겨버려 디자인만 따로 확인하기 어렵다는 요청으로
// 만든 격리 사본들 - 세션/백엔드 의존 전혀 없음. 확인 끝나면 이 블록 + 아래 라우트들
// + _test.tsx 파일들 지울 것. (DiagnosisStep4는 같은 이름의 무관한 기존 스크래치
// 파일이 이미 있어서 이번 배치에서 제외 - App.tsx 하단 라우트 주석 참고)
import DiagnosisSelectTest from "./pages/diagnosis/_backup/DiagnosisSelect_test";
import DiagnosisStep2Test from "./pages/diagnosis/_backup/DiagnosisStep2_test";
import DiagnosisStep3Test from "./pages/diagnosis/_backup/DiagnosisStep3_test";
import DiagnosisStep5Test from "./pages/diagnosis/_backup/DiagnosisStep5_test";
import DiagnosisStep6Test from "./pages/diagnosis/_backup/DiagnosisStep6_test";
import DiagnosisStep7Test from "./pages/diagnosis/_backup/DiagnosisStep7_test";
import DiagnosisStep8Test from "./pages/diagnosis/_backup/DiagnosisStep8_test";
import DiagnosisStep9Test from "./pages/diagnosis/_backup/DiagnosisStep9_test";
import DiagnosisIndustryResultTest from "./pages/diagnosis/_backup/DiagnosisIndustryResult_test";
// [2026-09-13, 디자인 검토용, 라이브 미적용] "업종코드를 찾았어요" 화면을 프로토타입
// 실측값대로 다시 만든 미리보기 - 검토 후 괜찮으면 DiagnosisIndustryResult.tsx에
// 반영하고 이 줄+아래 라우트+파일 정리할 것. 상세 이유는 파일 자체 주석 참고.
import DiagnosisIndustryResultPreview from "./pages/diagnosis/_backup/DiagnosisIndustryResultPreview";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 공개 라우트 - 로그인 없이 접근 가능한 딱 3개(입구) */}
        <Route path="/" element={<Splash />} />
        <Route path="/login" element={<LoginForm variant="user" />} />
        <Route path="/signup" element={<Signup />} />

        {/* [2026-09-15, 사용자 확인] "로그인 안 하면 서비스 자체를 못 쓴다" 원칙 -
            실제 서비스 화면은 전부 RequireAuth로 감싼다(관리자는 AdminRoute가 따로 담당).
            테스트/디자인 참고/미리보기 라우트(아래 나머지 전부)는 팀 공용 확인 용도라 제외. */}
        <Route element={<RequireAuth />}>
          <Route path="/home" element={<Home />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/diagnosis/choice" element={<DiagnosisChoice />} />
          <Route path="/matching" element={<MatchingList />} />
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
          {/* [2026-09-12] 메인 흐름 - DiagnosisStep5.tsx가 Q6 제출 후 여기로 이동시킨다
              (위 import 주석 참고). emkim99님 화면 디자인을 이쪽으로 옮겨 입히는 작업 진행 중. */}
          <Route path="/diagnosis/summary" element={<DiagnosisAnswerSummary />} />
          <Route path="/diagnosis/industry-result" element={<DiagnosisIndustryResult />} />
          <Route path="/diagnosis/report" element={<DiagnosisReport />} />
          {/* [2026-09-13] 마이페이지 "분석 리포트"에서 지난 세션을 다시 열어볼 때 - 같은
              컴포넌트가 URL의 sessionId 유무로 "진행 중" vs "완료된 리포트 보기"를 가른다. */}
          <Route path="/diagnosis/report/:sessionId" element={<DiagnosisReport />} />
          <Route path="/diagnosis/7" element={<DiagnosisStep6 />} />
          <Route path="/diagnosis/8" element={<DiagnosisStep7 />} />
          <Route path="/diagnosis/9" element={<DiagnosisStep8 />} />
          <Route path="/diagnosis/10" element={<DiagnosisStep9 />} />
        </Route>

        {/* [2026-09-12] 디자인 검토 완료 - 실제 /matching(MatchingList.tsx)에 반영됨.
            이 사본 자체는 팀원 참고용으로 당분간 남겨둠. */}
        <Route path="/matching-draft" element={<MatchingListDraft />} />
        <Route path="/edit-v2" element={<ProfileEditV2 />} />
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
        <Route path="/dev/report-summary-fixed-layout-test" element={<DiagnosisReportSummaryFixedLayoutTest />} />
        <Route path="/dev/ocr-popup-preview" element={<OcrPopupPreview />} />
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
