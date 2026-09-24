import { Link } from "react-router-dom";
import { CATEGORY_LABEL, fmtDate, placeholderFor } from "../lib/api";

function Meta({ c }) {
  if (c.type === "paper") {
    const a = c.authors || [];
    const who = a.length ? (a.length > 3 ? `${a[0]} 외 ${a.length - 1}명` : a.join(", ")) : null;
    return <div className="card-meta t-meta">{[who, c.venue, fmtDate(c.publishedAt || c.collectedAt)].filter(Boolean).join(" · ")}</div>;
  }
  return <div className="card-meta t-meta">{fmtDate(c.publishedAt || c.collectedAt)}</div>;
}

function Badges({ c }) {
  return (
    <div className="badges">
      <span className={`badge badge--${c.type}`}>{c.type === "paper" ? "논문" : "뉴스"}</span>
      {c.type !== "paper" && <span className="tag">{CATEGORY_LABEL[c.category] || c.category}</span>}
      {c.type === "paper" && c.sectionExtractStatus && (
        <span className={`badge ${c.sectionExtractStatus === "full" ? "badge--paper" : "badge--warn"}`}>
          {c.sectionExtractStatus === "full" ? "전문 분석" : "초록만"}
        </span>
      )}
    </div>
  );
}

// 카드 전체가 하나의 링크다. 별도 "원문 이동 버튼"을 두지 않는다 (C-4 해소).
export function Card({ c }) {
  const inner = (
    <>
      {c.type !== "paper" && (
        <img className="thumb" src={c.thumbnailUrl || placeholderFor(c.id)} alt=""
             aria-hidden="true" loading="lazy"
             onError={(e) => { e.currentTarget.src = placeholderFor(c.id); }} />
      )}
      <div className="card-body">
        <Badges c={c} />
        <h3 className="card-title t-card">{c.titleDisplay}</h3>
        {c.summaryDisplay && <p className="card-sum t-body">{c.summaryDisplay}</p>}
        <Meta c={c} />
      </div>
    </>
  );
  const cls = `card${c.type === "paper" ? " card--paper" : ""}`;
  // 논문은 사이트 내 상세로, 뉴스는 외부 원문으로 (FR-17 / FR-17a)
  return c.type === "paper"
    ? <Link className={cls} to={`/papers/${c.id}`}>{inner}</Link>
    : <a className={cls} href={c.sourceUrl} target="_blank" rel="noopener noreferrer">{inner}</a>;
}

export function Row({ c }) {
  const inner = (
    <>
      {c.type !== "paper" && (
        <img className="row-thumb" src={c.thumbnailUrl || placeholderFor(c.id)} alt=""
             aria-hidden="true" loading="lazy"
             onError={(e) => { e.currentTarget.src = placeholderFor(c.id); }} />
      )}
      <div className="row-body">
        <Badges c={c} />
        <h3 className="card-title t-card">{c.titleDisplay}</h3>
        {c.summaryDisplay && <p className="card-sum t-body">{c.summaryDisplay}</p>}
        <Meta c={c} />
      </div>
    </>
  );
  const cls = `row${c.type === "paper" ? " row--paper" : ""}`;
  return c.type === "paper"
    ? <Link className={cls} to={`/papers/${c.id}`}>{inner}</Link>
    : <a className={cls} href={c.sourceUrl} target="_blank" rel="noopener noreferrer">{inner}</a>;
}
