import { Suspense, lazy, useEffect, useState } from "react";
import { SearchBar } from "./SearchBar";

// 3D 는 데스크톱에서만. 모바일은 정적 SVG 폴백 (design-system §6).
const Scene = lazy(() => import("./Scene"));

export function Hero() {
  const [use3d, setUse3d] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setUse3d(mq.matches && !reduce.matches);
    update();
    mq.addEventListener("change", update);
    reduce.addEventListener("change", update);
    return () => { mq.removeEventListener("change", update); reduce.removeEventListener("change", update); };
  }, []);

  return (
    <section className="hero">
      <div className="hero-canvas" aria-hidden="true">
        {use3d ? <Suspense fallback={null}><Scene /></Suspense> : <StaticNodes />}
      </div>
      <div className="container hero-in">
        <h1 className="hero-copy t-display">최신 보안 동향과 글로벌 논문을 한눈에</h1>
        <p className="hero-sub t-body">
          매일 두 번, 국내외 보안 뉴스와 arXiv 논문을 모아 한국어로 옮깁니다.
        </p>
        <div className="hero-search">
          <SearchBar variant="hero" autoFocusOnDesktop />
        </div>
      </div>
    </section>
  );
}

// 모바일·모션저감용 정적 폴백. 3D 와 같은 모티프(노드 토폴로지), 무채색.
function StaticNodes() {
  const pts = [[12,30],[26,62],[38,22],[52,48],[64,18],[72,58],[86,34],[94,70],
               [20,84],[44,78],[58,88],[80,86]];
  return (
    <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice"
         style={{ opacity: .5 }}>
      {pts.map(([x, y], i) => pts.slice(i + 1).map(([x2, y2], j) => {
        const d = Math.hypot(x - x2, y - y2);
        return d < 26 ? <line key={`${i}-${j}`} x1={x} y1={y} x2={x2} y2={y2}
          stroke="var(--border-strong)" strokeWidth=".25" /> : null;
      }))}
      {pts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i % 7 === 0 ? 1.3 : 1}
                fill={i % 7 === 0 ? "var(--point)" : "var(--border-strong)"} />
      ))}
    </svg>
  );
}
