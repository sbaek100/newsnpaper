import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth";
import { ErrorBox, SkeletonList } from "../components/States";
import { fmtDate } from "../lib/api";

export default function Admin() {
  const { authed } = useAuth();
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);

  const load = () => Promise.all([
    authed("/admin/sources"), authed("/admin/batches"), authed("/admin/signups"),
  ]).then(([s, b, g]) => setD({ ...s, ...b, ...g })).catch((e) => setErr(e.message));

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [authed]);

  async function act(id, what) {
    await authed(`/admin/signups/${id}/${what}`, { method: "POST" });
    load();
  }

  async function toggle(id, enabled) {
    await authed(`/admin/sources/${id}?enabled=${!enabled}`, { method: "PUT" });
    load();
  }

  if (err) return <div className="container section"><ErrorBox message={err} /></div>;
  if (!d) return <div className="container section"><SkeletonList /></div>;

  return (
    <div className="container section">
      <h1 className="t-h1" style={{ marginTop: 0 }}>관리</h1>

      {/* 가입 승인 — PRD-01 FR-20 */}
      <h2 className="t-h2">
        가입 신청
        {d.signups.filter((x) => x.status === "pending_approval").length > 0 && (
          <span className="badge badge--warn" style={{ marginLeft: 8 }}>
            승인 대기 {d.signups.filter((x) => x.status === "pending_approval").length}
          </span>
        )}
      </h2>
      <div className="list" style={{ marginBottom: 40 }}>
        {!d.signups.length && <p className="t-meta" style={{ color: "var(--text-disabled)" }}>
          대기 중인 신청이 없습니다.</p>}
        {d.signups.map((u) => (
          <div key={u.id} className="row" style={{ alignItems: "center" }}>
            <div className="row-body" style={{ flex: 1 }}>
              <div className="badges">
                <span className={`badge badge--${
                  u.status === "pending_approval" ? "warn"
                  : u.status === "rejected" ? "danger" : "news"}`}>
                  {u.status === "pending_email" ? "이메일 인증 대기"
                   : u.status === "pending_approval" ? "승인 대기" : "거부됨"}
                </span>
                <span className="t-meta">{fmtDate(u.created_at)}</span>
              </div>
              <strong>{u.email}</strong>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {u.status !== "pending_email" && (
                <button className="btn btn--primary"
                        onClick={() => act(u.id, "approve")}>승인</button>
              )}
              {u.status !== "rejected" && (
                <button className="btn" onClick={() => act(u.id, "reject")}>거부</button>
              )}
            </div>
          </div>
        ))}
      </div>

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
