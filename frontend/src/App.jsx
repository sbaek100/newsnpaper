import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Gnb } from "./components/Gnb";
import { Empty } from "./components/States";
import { AuthProvider, useAuth } from "./lib/auth";
import Main from "./pages/Main";
import ListPage from "./pages/ListPage";
import PaperDetail from "./pages/PaperDetail";
import Login from "./pages/Login";
import Verify from "./pages/Verify";
import Resend from "./pages/Resend";
import Feed from "./pages/Feed";
import Admin from "./pages/Admin";
import { Keywords, ChangePassword } from "./pages/Account";
import "./styles/tokens.css";
import "./styles/app.css";

// 🔴 화면 가드는 편의일 뿐이다. 실제 권한은 서버가 강제한다 (PRD-01 FR-5).
function Private({ children, admin = false }) {
  const { user, ready } = useAuth();
  if (!ready) return <div className="container section"><div className="skel" style={{ height: 200 }} /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (admin && user.role !== "admin")
    return <div className="container section"><Empty title="관리자만 접근할 수 있습니다" /></div>;
  return children;
}

function Shell() {
  return (
    <>
      <Gnb />
      <main>
        <Routes>
          <Route path="/" element={<Main />} />
          <Route path="/search" element={<ListPage searchMode />} />
          <Route path="/news/international" element={<ListPage title="국제 뉴스" fixed={{ category: "international" }} />} />
          <Route path="/news/domestic" element={<ListPage title="국내 뉴스" fixed={{ category: "domestic" }} />} />
          <Route path="/papers" element={<ListPage title="최신 논문" fixed={{ type: "paper" }} />} />
          <Route path="/papers/:id" element={<PaperDetail />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Login mode="signup" />} />
          <Route path="/signup/resend" element={<Resend />} />
          <Route path="/verify" element={<Verify />} />
          <Route path="/feed" element={<Private><Feed /></Private>} />
          <Route path="/account/keywords" element={<Private><Keywords /></Private>} />
          <Route path="/account/password" element={<Private><ChangePassword /></Private>} />
          <Route path="/admin" element={<Private admin><Admin /></Private>} />
          <Route path="*" element={<div className="container section"><Empty title="페이지를 찾을 수 없습니다" /></div>} />
        </Routes>
      </main>
      <footer style={{ borderTop: "1px solid var(--border)", padding: "32px 0",
                       color: "var(--text-tertiary)", fontSize: 13 }}>
        <div className="container">secubrief · 개인용 보안 뉴스·논문 큐레이션</div>
      </footer>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter><AuthProvider><Shell /></AuthProvider></BrowserRouter>
  );
}
