import { Row } from "./Card";
import { SkeletonList, ErrorBox, Empty } from "./States";

export function ListView({ state, empty }) {
  if (state.loading) return <SkeletonList />;
  if (state.error) return <ErrorBox message={state.error} onRetry={state.retry} />;
  if (!state.data?.items?.length) return empty;
  return (
    <div className="list">
      {state.data.items.map((c) => <Row key={c.id} c={c} />)}
    </div>
  );
}

export function Pager({ page, size, total, onChange }) {
  const last = Math.max(1, Math.ceil(total / size));
  if (last <= 1) return null;
  const from = Math.max(1, Math.min(page - 2, last - 4));
  const nums = Array.from({ length: Math.min(5, last) }, (_, i) => from + i).filter((n) => n <= last);
  return (
    <nav className="pager" aria-label="페이지">
      <button onClick={() => onChange(page - 1)} disabled={page <= 1} aria-label="이전">‹</button>
      {nums.map((n) => (
        <button key={n} className={n === page ? "on" : ""} onClick={() => onChange(n)}
                aria-current={n === page ? "page" : undefined}>{n}</button>
      ))}
      <button onClick={() => onChange(page + 1)} disabled={page >= last} aria-label="다음">›</button>
    </nav>
  );
}

export function Filters({ type, kw, onType, onKw }) {
  const KWS = ["보안", "해킹", "사이버", "AI"];
  return (
    <div className="filters">
      {[["", "전체"], ["news", "뉴스"], ["paper", "논문"]].map(([v, label]) => (
        <button key={v} className={`chip${type === v ? " on" : ""}`}
                aria-pressed={type === v} onClick={() => onType(v)}>{label}</button>
      ))}
      <span style={{ width: 1, background: "var(--border)", margin: "0 4px" }} />
      {KWS.map((k) => (
        <button key={k} className={`chip${kw.includes(k) ? " on" : ""}`}
                aria-pressed={kw.includes(k)}
                onClick={() => onKw(kw.includes(k) ? kw.filter((x) => x !== k) : [...kw, k])}>
          {k}
        </button>
      ))}
    </div>
  );
}
