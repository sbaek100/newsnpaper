import { NavLink } from "react-router-dom";
import { SearchBar } from "./SearchBar";

export function Gnb() {
  return (
    <header className="gnb">
      <div className="container gnb-in">
        <NavLink to="/" className="logo">secubrief</NavLink>
        <nav className="gnb-nav">
          <NavLink to="/news/international" className={({isActive}) => isActive ? "on" : ""}>국제 뉴스</NavLink>
          <NavLink to="/news/domestic" className={({isActive}) => isActive ? "on" : ""}>국내 뉴스</NavLink>
          <NavLink to="/papers" className={({isActive}) => isActive ? "on" : ""}>최신 논문</NavLink>
        </nav>
        <div className="gnb-right" style={{ flex: "1 1 auto", maxWidth: 320 }}>
          <div style={{ flex: 1 }}><SearchBar /></div>
        </div>
      </div>
    </header>
  );
}
