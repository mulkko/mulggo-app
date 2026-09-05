import { BrowserRouter, Route, Routes } from "react-router-dom";
import Main from "./pages";
import Signup from "./pages/auth/Signup";
import LoginForm from "./components/LoginForm";
import AdminHome from "./pages/admin/AdminHome";
import AdminMembers from "./pages/admin/AdminMembers";
import AdminLayout from "./pages/admin/AdminLayout";
import AdminRoute from "./pages/admin/AdminRoute";
import AdminStyleGuide from "./components/AdminStyleGuide/AdminStyleGuide";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Main />} />
        <Route path="/login" element={<LoginForm variant="user" />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/style-guide" element={<AdminStyleGuide />} />
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
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
