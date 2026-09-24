import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

export function SearchBar({ variant }) {
  const [sp] = useSearchParams();
  const [v, setV] = useState(sp.get("q") || "");
  const nav = useNavigate();

  // GNB 검색창과 Hero 검색 바가 같은 검색을 실행한다 (PRD-05 FR-14)
  function submit(e) {
    e.preventDefault();
    const q = v.trim();
    if (q.length < 2) return;
    nav(`/search?q=${encodeURIComponent(q)}`);
  }

  return (
    <form className={`search${variant === "hero" ? " search--hero" : ""}`} onSubmit={submit}
          role="search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"
           stroke="var(--text-disabled)" strokeWidth="2">
        <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
      </svg>
      <input value={v} onChange={(e) => setV(e.target.value)}
             placeholder="제목·요약·논문 초록에서 검색"
             aria-label="검색어" />
    </form>
  );
}
