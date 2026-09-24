import { useState } from "react";
import { useParams } from "react-router-dom";
import { api, fmtDate } from "../lib/api";
import { useApi } from "../lib/useApi";
import { ErrorBox, Empty } from "../components/States";

const LABEL = { Abstract: "초록", Introduction: "서론", Conclusion: "결론" };
const ORDER = ["Abstract", "Introduction", "Conclusion"];

export default function PaperDetail() {
  const { id } = useParams();
  const s = useApi(() => api.paper(id), [id]);
  const [allOriginal, setAllOriginal] = useState(false);
  const [perSec, setPerSec] = useState({});

  if (s.loading) return <div className="container section"><div className="skel" style={{ height: 400 }} /></div>;
  if (s.error) return <div className="container section"><Empty title="논문을 찾을 수 없습니다" /></div>;

  const p = s.data;
  const has = new Set((p.sections || []).map((x) => x.name));
  const missing = ORDER.filter((n) => !has.has(n));

  return (
    <div className="container">
      <header className="paper-head">
        <div className="badges" style={{ marginBottom: 12 }}>
          <span className="badge badge--paper">논문</span>
          {p.sectionExtractStatus === "full"
            ? <span className="badge badge--paper">전문 분석</span>
            : <span className="badge badge--warn">초록만</span>}
          {p.translationStatus === "failed" && <span className="badge badge--danger">번역 실패</span>}
        </div>
        <h1 className="t-h1" style={{ margin: "0 0 8px" }}>{p.titleDisplay}</h1>
        {p.titleOriginal !== p.titleDisplay && (
          <p className="t-body" style={{ color: "var(--text-tertiary)", margin: "0 0 12px" }}>
            {p.titleOriginal}
          </p>
        )}
        <div className="paper-meta t-meta">
          {p.authors?.length > 0 && <span>{p.authors.slice(0, 5).join(", ")}
            {p.authors.length > 5 ? ` 외 ${p.authors.length - 5}명` : ""}</span>}
          {p.venue && <span>{p.venue}</span>}
          <span>{fmtDate(p.publishedAt || p.collectedAt)}</span>
          {p.arxivId && <span>arXiv:{p.arxivId}</span>}
          {p.doi && <span>DOI:{p.doi}</span>}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 20, flexWrap: "wrap" }}>
          <a className="btn btn--primary" href={p.pdfUrl || p.sourceUrl}
             target="_blank" rel="noopener noreferrer">원문 PDF 열기 ↗</a>
          <button className="btn" aria-pressed={allOriginal}
                  onClick={() => { setAllOriginal(!allOriginal); setPerSec({}); }}>
            {allOriginal ? "번역문 보기" : "전체 원문 보기"}
          </button>
        </div>
      </header>

      {p.translationStatus === "failed" && (
        <div className="error-box" style={{ marginTop: 24 }}>
          번역에 실패해 원문을 표시합니다.
        </div>
      )}

      {(p.sections || []).map((sec) => {
        const orig = perSec[sec.name] ?? allOriginal;
        const body = orig ? sec.textOriginal : (sec.textKo || sec.textOriginal);
        return (
          <section className="sec" key={sec.name}>
            <div className="sec-head">
              <h2 className="t-h2" style={{ margin: 0 }}>{LABEL[sec.name] || sec.name}</h2>
              {sec.textKo && (
                <button className="btn" style={{ marginLeft: "auto" }} aria-pressed={orig}
                        onClick={() => setPerSec({ ...perSec, [sec.name]: !orig })}>
                  {orig ? "번역" : "원문"}
                </button>
              )}
            </div>
            <p className="t-reading" style={{ margin: 0 }}>{body}</p>
          </section>
        );
      })}

      {missing.length > 0 && (
        <div className="notice" style={{ margin: "32px 0" }}>
          전문을 확보하지 못해 {missing.map((n) => LABEL[n]).join("·")}은 제공하지 않습니다.
        </div>
      )}
    </div>
  );
}
