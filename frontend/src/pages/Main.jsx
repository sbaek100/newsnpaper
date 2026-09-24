import { Link } from "react-router-dom";
import { Hero } from "../components/Hero";
import { Card } from "../components/Card";
import { SkeletonGrid, ErrorBox, Empty } from "../components/States";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";

function Section({ title, more, items, loading, error, retry }) {
  return (
    <section className="section">
      <div className="container">
        <div className="section-head">
          <h2 className="t-h1" style={{ margin: 0 }}>{title}</h2>
          <Link className="section-more" to={more}>더보기 →</Link>
        </div>
        {loading ? <SkeletonGrid n={3} />
          : error ? <ErrorBox message={error} onRetry={retry} />
          : !items?.length ? <Empty title="아직 수집된 항목이 없습니다" />
          : <div className="grid">{items.map((c) => <Card key={c.id} c={c} />)}</div>}
      </div>
    </section>
  );
}

export default function Main() {
  const s = useApi(() => api.main(), []);
  return (
    <>
      <Hero />
      {/* 뉴스 영역 → 논문 영역 순서 (PRD-04 FR-13) */}
      <Section title="최신 보안 뉴스" more="/news/international"
               items={s.data?.news} loading={s.loading} error={s.error} retry={s.retry} />
      <div style={{ background: "var(--bg-subtle)" }}>
        <Section title="최신 논문" more="/papers"
                 items={s.data?.papers} loading={s.loading} error={s.error} retry={s.retry} />
      </div>
    </>
  );
}
