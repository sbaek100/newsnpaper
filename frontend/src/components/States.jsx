// 상태 화면 — 로딩은 스켈레톤(스피너 금지), 빈 상태는 텍스트만(일러스트 금지). design-system §7

export function SkeletonGrid({ n = 6 }) {
  return (
    <div className="grid" aria-busy="true" aria-label="불러오는 중">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="skel" style={{ height: 300 }} />
      ))}
    </div>
  );
}

export function SkeletonList({ n = 5 }) {
  return (
    <div className="list" aria-busy="true" aria-label="불러오는 중">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="skel" style={{ height: 120 }} />
      ))}
    </div>
  );
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="error-box">
      <p style={{ margin: "0 0 12px" }}>{message}</p>
      {onRetry && <button className="btn" onClick={onRetry}>다시 시도</button>}
    </div>
  );
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      <p className="t-h2" style={{ margin: "0 0 8px", color: "var(--text)" }}>{title}</p>
      {children}
    </div>
  );
}
