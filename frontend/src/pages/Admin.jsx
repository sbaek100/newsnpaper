import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth";
import { ErrorBox, SkeletonList } from "../components/States";
import { fmtDate } from "../lib/api";

export default function Admin() {
  const { authed } = useAuth();
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);

  const load = () => Promise.all([authed("/admin/sources"), authed("/admin/batches")])
    .then(([s, b]) => setD({ ...s, ...b })).catch((e) => setErr(e.message));

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [authed]);

  async function toggle(id, enabled) {
    await authed(`/admin/sources/${id}?enabled=${!enabled}`, { method: "PUT" });
    load();
  }

  if (err) return <div className="container section"><ErrorBox message={err} /></div>;
  if (!d) return <div className="container section"><SkeletonList /></div>;

  return (
    <div className="container section">
      <h1 className="t-h1" style={{ marginTop: 0 }}>관리</h1>

      <h2 className="t-h2">수집 소스 ({d.sources.length})</h2>
      <div className="list" style={{ marginBottom: 40 }}>
        {d.sources.map((s) => (
          <div key={s.id} className="row" style={{ alignItems: "center" }}>
            <div className="row-body" style={{ flex: 1 }}>
              <div className="badges">
                <span className="tag">{s.kind}</span>
                <span className="tag">{s.category}</span>
              </div>
              <strong>{s.name}</strong>
              <span className="t-meta" style={{ color: "var(--text-tertiary)",
                    overflow: "hidden", textOverflow: "ellipsis" }}>{s.url}</span>
            </div>
            <button className="btn" aria-pressed={s.enabled}
                    onClick={() => toggle(s.id, s.enabled)}>
              {s.enabled ? "사용 중" : "중지됨"}
            </button>
          </div>
        ))}
      </div>

      <h2 className="t-h2">
        배치 실행 이력
        {d.translationFailed > 0 && (
          <span className="badge badge--danger" style={{ marginLeft: 8 }}>
            번역 실패 {d.translationFailed}
          </span>
        )}
      </h2>
      {d.translationFailed > 0 && (
        <button className="btn" style={{ marginBottom: 12 }}
                onClick={() => authed("/admin/translations/retry", { method: "POST" }).then(load)}>
          실패 건 재시도
        </button>
      )}
      <div className="list">
        {d.batches.map((b) => (
          <div key={b.id} className="row">
            <div className="row-body">
              <div className="badges">
                <span className={`badge badge--${b.status === "done" ? "paper" : b.status === "failed" ? "danger" : "warn"}`}>
                  {b.status}
                </span>
                <span className="t-meta">{fmtDate(b.started_at)}</span>
              </div>
              <pre className="t-meta" style={{ margin: 0, whiteSpace: "pre-wrap",
                    color: "var(--text-secondary)" }}>
                {b.stats ? JSON.stringify(b.stats) : "—"}
              </pre>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
