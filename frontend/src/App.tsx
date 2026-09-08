import { BrowserRouter, Route, Routes } from "react-router-dom";
import Splash from "./pages/splash/Splash";
import Signup from "./pages/auth/Signup";
import LoginForm from "./components/LoginForm";
import AdminHome from "./pages/admin/AdminHome";
import AdminMembers from "./pages/admin/AdminMembers";
import AnnouncementsSync from "./pages/admin/AnnouncementsSync";
import AdminLayout from "./pages/admin/AdminLayout";
import AdminRoute from "./pages/admin/AdminRoute";
import AdminStyleGuide from "./components/AdminStyleGuide/AdminStyleGuide";
import WebStyleGuide from "./components/WebStyleGuide/WebStyleGuide";
import MatchingList from "./pages/matching/MatchingList";
import MatchingDetail from "./pages/matching/MatchingDetail";
import DocPreview from "./pages/matching/DocPreview";
import FilterPage from "./pages/matching/FilterPage";
import MyPage from "./pages/mypage/MyPage";
import ProfileEdit from "./pages/mypage/ProfileEdit";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Splash />} />
        <Route path="/login" element={<LoginForm variant="user" />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/matching" element={<MatchingList />} />
        <Route path="/matching/filter" element={<FilterPage />} />
        <Route path="/matching/:id" element={<MatchingDetail />} />
        <Route path="/matching/:id/doc-preview" element={<DocPreview />} />
        <Route path="/mypage" element={<MyPage />} />
        <Route path="/mypage/edit" element={<ProfileEdit />} />
        <Route path="/style-guide" element={<AdminStyleGuide />} />
        <Route path="/dev/web-style-guide" element={<WebStyleGuide />} />
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
