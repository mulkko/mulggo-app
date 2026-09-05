import { BrowserRouter, Route, Routes } from "react-router-dom";
import Main from "./pages";
import Login from "./pages/auth/Login";
import Signup from "./pages/auth/Signup";
import AdminLogin from "./pages/admin/AdminLogin";
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
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/style-guide" element={<AdminStyleGuide />} />
        <Route path="/admin/login" element={<AdminLogin />} />
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
