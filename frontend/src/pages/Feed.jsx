import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Row } from "../components/Card";
import { Pager } from "../components/ListView";
import { SkeletonList, ErrorBox, Empty } from "../components/States";

// PRD-06 §9.5 — 목록 레이아웃을 재사용한다. 헤더 문구와 0건 안내만 다르다.
export default function Feed() {
  const { authed } = useAuth();
  const [page, setPage] = useState(1);
  const [s, setS] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    let alive = true;
    setS((x) => ({ ...x, loading: true }));
    authed(`/me/feed?page=${page}&size=20`)
      .then((d) => alive && setS({ loading: false, error: null, data: d }))
      .catch((e) => alive && setS({ loading: false, error: e.message, data: null }));
    return () => { alive = false; };
  }, [authed, page]);

  return (
    <div className="container section">
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 className="t-h1" style={{ margin: 0 }}>내 피드</h1>
        <Link className="section-more" to="/account/keywords">키워드 관리 →</Link>
      </div>
      <p className="t-meta scope" aria-live="polite" style={{ margin: "4px 0 20px" }}>
        {s.data ? `${s.data.total}건 · ${s.data.appliedScope}` : " "}
      </p>

      {s.loading ? <SkeletonList />
        : s.error ? <ErrorBox message={s.error} />
        : !s.data.items.length ? (
          <Empty title="표시할 항목이 없습니다">
            {/* PRD-01 FR-9 — 기본 수집 범위 밖일 수 있음을 알린다 */}
            <p style={{ margin: "0 0 4px" }}>
              수집은 보안·해킹·사이버·AI 네 키워드로만 이뤄집니다.
            </p>
            <p style={{ margin: 0 }}>구독 키워드가 그 범위 밖이면 결과가 비어 있을 수 있습니다.</p>
            <p style={{ marginTop: 16 }}>
              <Link className="btn" to="/account/keywords">키워드 설정하기</Link>
            </p>
          </Empty>
        ) : <div className="list">{s.data.items.map((c) => <Row key={c.id} c={c} />)}</div>}

      {s.data && <Pager page={page} size={20} total={s.data.total} onChange={setPage} />}
    </div>
  );
}
