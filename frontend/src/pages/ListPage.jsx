import { useSearchParams } from "react-router-dom";
import { ListView, Pager, Filters } from "../components/ListView";
import { Empty } from "../components/States";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";

// 검색·카테고리 목록·피드가 이 컴포넌트 하나를 공유한다 (PRD-06 L-1).
export default function ListPage({ title, fixed = {}, searchMode = false }) {
  const [sp, setSp] = useSearchParams();
  const q = sp.get("q") || "";
  const page = Number(sp.get("page") || 1);
  const type = sp.get("type") || "";
  const kw = (sp.get("kw") || "").split(",").filter(Boolean);
  const size = 20;

  // 필터·정렬·페이지를 URL 에 반영한다 (PRD-06 FR-6)
  const patch = (o) => {
    const n = new URLSearchParams(sp);
    Object.entries(o).forEach(([k, v]) => (v ? n.set(k, v) : n.delete(k)));
    if (!("page" in o)) n.delete("page");
    setSp(n);
  };

  const params = { q: q || undefined, page, size, ...fixed,
                   type: fixed.type || type || undefined,
                   kw: kw.length ? kw.join(",") : undefined };
  const s = useApi(() => api.contents(params), [JSON.stringify(params)]);

  const heading = searchMode ? (q ? `‘${q}’ 검색 결과` : "검색") : title;

  return (
    <div className="container section">
      <h1 className="t-h1" style={{ margin: "0 0 4px" }}>{heading}</h1>
      <p className="t-meta scope" aria-live="polite" style={{ margin: "0 0 20px" }}>
        {s.data ? `${s.data.total}건` : " "}
        {/* 검색 범위를 숨기지 않는다 — 한국어 질의는 논문 본문에 닿지 못한다 (PRD-06 FR-10) */}
        {s.data && q ? ` · 검색 범위: ${s.data.appliedScope}` : ""}
      </p>

      {!fixed.type && <Filters type={type} kw={kw}
        onType={(v) => patch({ type: v })} onKw={(v) => patch({ kw: v.join(",") })} />}

      <ListView state={s} empty={
        <Empty title={q ? "검색 결과가 없습니다" : "아직 수집된 항목이 없습니다"}>
          {q && <>
            <p style={{ margin: "0 0 4px" }}>검색 범위: {s.data?.appliedScope}</p>
            <p style={{ margin: 0 }}>기사 본문은 저장하지 않아 제목·요약·초록에서만 찾습니다.</p>
          </>}
        </Empty>
      } />

      {s.data && <Pager page={page} size={size} total={s.data.total}
        onChange={(n) => patch({ page: n > 1 ? String(n) : "" })} />}
    </div>
  );
}
