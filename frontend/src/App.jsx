import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Gnb } from "./components/Gnb";
import { Empty } from "./components/States";
import Main from "./pages/Main";
import ListPage from "./pages/ListPage";
import PaperDetail from "./pages/PaperDetail";
import "./styles/tokens.css";
import "./styles/app.css";

export default function App() {
  return (
    <BrowserRouter>
      <Gnb />
      <main>
        <Routes>
          <Route path="/" element={<Main />} />
          <Route path="/search" element={<ListPage searchMode />} />
          <Route path="/news/international" element={
            <ListPage title="국제 뉴스" fixed={{ category: "international" }} />} />
          <Route path="/news/domestic" element={
            <ListPage title="국내 뉴스" fixed={{ category: "domestic" }} />} />
          <Route path="/papers" element={
            <ListPage title="최신 논문" fixed={{ type: "paper" }} />} />
          <Route path="/papers/:id" element={<PaperDetail />} />
          <Route path="*" element={
            <div className="container section"><Empty title="페이지를 찾을 수 없습니다" /></div>} />
        </Routes>
      </main>
      <footer style={{ borderTop: "1px solid var(--border)", padding: "32px 0",
                       color: "var(--text-tertiary)", fontSize: 13 }}>
        <div className="container">secubrief · 개인용 보안 뉴스·논문 큐레이션</div>
      </footer>
    </BrowserRouter>
  );
}
