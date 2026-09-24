import { NavLink, useNavigate } from "react-router-dom";
import { SearchBar } from "./SearchBar";
import { useAuth } from "../lib/auth";

export function Gnb() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  return (
    <header className="gnb">
      <div className="container gnb-in">
        <NavLink to="/" className="logo">secubrief</NavLink>
        <nav className="gnb-nav">
          <NavLink to="/news/international" className={({isActive}) => isActive ? "on" : ""}>국제 뉴스</NavLink>
          <NavLink to="/news/domestic" className={({isActive}) => isActive ? "on" : ""}>국내 뉴스</NavLink>
          <NavLink to="/papers" className={({isActive}) => isActive ? "on" : ""}>최신 논문</NavLink>
          {/* 역할에 따라 진입점만 달라진다. 콘텐츠는 같다 (PRD-04 §3). */}
          {user && <NavLink to="/feed" className={({isActive}) => isActive ? "on" : ""}>내 피드</NavLink>}
          {user?.role === "admin" && <NavLink to="/admin" className={({isActive}) => isActive ? "on" : ""}>관리</NavLink>}
        </nav>
        <div className="gnb-right" style={{ flex: "1 1 auto", maxWidth: 380 }}>
          <div style={{ flex: 1, minWidth: 0 }}><SearchBar /></div>
          {user ? (
            <button className="btn" onClick={() => logout().then(() => nav("/"))}>로그아웃</button>
          ) : (
            <>
              <NavLink className="btn" to="/login">로그인</NavLink>
              <NavLink className="btn btn--primary gnb-signup" to="/signup">가입 신청</NavLink>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
