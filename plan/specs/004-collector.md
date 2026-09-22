# SPEC-004: 수집 파이프라인

| 항목 | 값 |
|---|---|
| 근거 | roadmap.md 단계 3, PRD-03 §3·§4·§7 |
| 목적 | 4종 소스에서 수집 → dedup → PDF 섹션 추출 → DB 저장 → 번역 큐 적재 |
| 선행 조건 | **SPEC-003 완료** (테이블이 있어야 한다) |
| 후행 | SPEC-005 번역 워커 |

## 1. 범위

| 만든다 | 만들지 않는다 |
|---|---|
| arXiv · Semantic Scholar 수집기 | 번역 실행 (→ SPEC-005) |
| RSS 7매체 · GDELT · Naver 수집기 | API 엔드포인트 (→ SPEC-006) |
| dedup (URL 정규화 + DOI/arXiv ID) | 화면 |
| PDF 다운로드 → 텍스트 추출 → 섹션 휴리스틱 | |
| APScheduler 09:00/21:00, `batch_runs` 기록 | |
| `translation_jobs` 적재 | |

## 2. 수집 소스 (PRD-03 §7)

### 2.1 논문

| ID | 요구사항 |
|---|---|
| C-1 | arXiv는 **`cs.CR` 전량을 1차로** 채우고, 남는 자리를 `cs.AI`·`cs.LG`의 키워드 교차 매칭분으로 채운다 (FR-35) |
| C-2 | Semantic Scholar는 영문 키워드 질의, `fieldsOfStudy=Computer Science` (FR-21) |
| C-3 | arXiv API는 호출 간 **3초 이상 간격**을 둔다 (arXiv 이용 약관) |
| C-4 | Semantic Scholar는 키 없이도 동작하되, `secrets/`에 키가 있으면 쓴다 |

### 2.2 뉴스

| ID | 요구사항 |
|---|---|
| C-5 | RSS 7매체는 `sources` 테이블에서 읽는다. 코드에 URL을 하드코딩하지 마라 (FR-37) |
| C-6 | 국제 API는 **GDELT 2.0 DOC** (키 불필요), 국내는 **Naver 검색 API(news)** (FR-36) |
| C-7 | Naver 키는 `secrets/naver_client_secret`에서 읽는다. 없으면 해당 소스만 건너뛰고 경고 (FR-25) |
| C-8 | 국내 소스는 한글 키워드, 국제는 영문 키워드로 질의한다 (PRD-03 §3.1) |

### 2.3 공통

| ID | 요구사항 |
|---|---|
| C-9 | **부분 실패 허용** — 한 소스가 죽어도 나머지는 계속한다 (FR-25) |
| C-10 | 소스별 성공/실패 건수를 `batch_runs.stats`에 기록한다 (FR-26) |
| C-11 | 수집 상한은 `.env`의 `BATCH_LIMIT_NEWS`(100) / `BATCH_LIMIT_PAPERS`(30) (FR-27) |
| C-12 | 상한 초과 시 **최신순으로 자른다** |
| C-13 | 매칭된 키워드를 `matched_keywords`에 전부 기록한다 (FR-33·FR-34) |

## 3. 🔴 dedup (PRD-03 FR-24, §4.2)

단순 URL 문자열 비교로는 부족하다.

| ID | 요구사항 |
|---|---|
| C-14 | URL 정규화 — 추적 파라미터(`utm_*`, `fbclid`, `gclid` 등) 제거, 프로토콜·호스트 소문자화, 말미 `/` 정리, 기본 포트 제거 |
| C-15 | 리다이렉트·단축 URL은 최종 URL을 해석한 뒤 비교한다 |
| C-16 | **논문은 DOI 또는 arXiv ID를 우선 키로** 쓴다. 같은 논문의 arXiv판과 Semantic Scholar판을 1건으로 합친다 |
| C-17 | 병합 시 **정보가 더 많은 쪽을 남긴다** (PDF URL·초록·저자가 있는 쪽) |
| C-18 | **같은 사건을 다룬 다른 매체 기사는 중복이 아니다.** 제목 유사도로 묶지 마라 |
| C-19 | 이미 DB에 있는 항목은 다시 수집하지 않는다 (재번역 방지) |

## 4. 🔴 PDF 섹션 추출 (PRD-03 §5.4, §5.7)

논문 PDF는 표준 구조가 없다. **실패를 전제로 설계한다.**

| ID | 요구사항 |
|---|---|
| C-20 | PyMuPDF 또는 pdfplumber로 텍스트를 추출한다. **GROBID를 쓰지 마라** (서비스 추가) |
| C-21 | 섹션 제목을 다중 패턴으로 매칭한다 — `Conclusion`, `Conclusions`, `Concluding Remarks`, `Discussion and Conclusion`, 번호 접두 `5. Conclusion`, 대문자 변형 등 (FR-17) |
| C-22 | **2단 조판 인식** — 컬럼을 무시하면 텍스트 순서가 뒤섞인다 (FR-18) |
| C-23 | 추출된 섹션이 비정상적으로 짧거나(< 200자) 길면(> 50,000자) **실패로 보고 폴백**한다 (FR-19) |
| C-24 | 실패 시 **Abstract만으로 폴백**하고 `section_extract_status='abstract_only'` (FR-15) |
| C-25 | Abstract조차 없으면 `'failed'` |
| C-26 | 섹션 추출 성공률을 `batch_runs.stats`에 집계한다 (FR-20) |
| C-27 | **전문을 `full_text_original`에 저장한다. 200,000자로 자른다** (FR-29·FR-52) |
| C-28 | PDF는 **텍스트 추출 직후 삭제한다** (FR-51). 임시 경로는 `papers_pdf/` |
| C-29 | PDF를 못 받으면 `full_text_status='no_pdf'`, Abstract로 진행 (FR-29b) |

## 5. 번역 큐 적재

| ID | 요구사항 |
|---|---|
| C-30 | 저장 후 번역이 필요한 필드마다 `translation_jobs` 행을 만든다 |
| C-31 | **이미 한국어인 콘텐츠는 큐에 넣지 않는다.** `translation_status='skipped'` (FR-10) |
| C-32 | 언어 판별은 휴리스틱으로 충분하다 (한글 문자 비율). 외부 언어감지 API를 쓰지 마라 |
| C-33 | 요약문이 없으면 제목만 큐에 넣는다. `summary_original=NULL` (FR-53) |
| C-34 | **`full_text_original`은 큐에 넣지 마라** — 번역 대상이 아니다 (FR-29a) |
| C-35 | 논문은 제목 + 섹션 3개 = 최대 4건, 뉴스는 제목 + 요약 = 최대 2건 |

## 6. 스케줄러

| ID | 요구사항 |
|---|---|
| C-36 | APScheduler로 `.env`의 `BATCH_TIMES`(기본 `09:00,21:00`) KST에 실행 (FR-38) |
| C-37 | 배치 시작 시 `batch_runs` 행을 만들고, 끝나면 `finished_at`·`status`를 채운다 |
| C-38 | 배치가 겹쳐 실행되지 않게 한다 (`max_instances=1`) |
| C-39 | 수동 실행 진입점도 둔다 — `python -m collector.run --once` |

## 7. 🔴 하드 제약

| 제약 | 내용 |
|---|---|
| 뉴스 본문 | **기사 본문을 스크래핑하지 마라** (PRD-03 FR-5, PRD-05 §4.1). RSS/API의 description 필드만 쓴다 |
| 외부 전송 | 수집 콘텐츠를 외부 API로 보내지 마라. 번역은 온프레미스다 (FR-13) |
| 아웃바운드 | PRD-02 §8의 허용 목록 밖으로 나가지 마라 |
| `robots.txt` | PDF 다운로드 시 `User-Agent`를 명시하고 과도한 병렬 요청을 하지 마라 |
| 번역 실행 | 이 명세에서 **번역을 실행하지 마라.** 큐 적재까지다 |
| 시크릿 | API 키를 코드·로그에 남기지 마라 (PRD-02 FR-17 — 쿼리스트링 키도 마스킹) |

## 8. 검증 방법

- [ ] `python -m collector.run --once --dry-run` 이 외부 호출 없이 구성을 검증한다
- [ ] 실제 1회 실행 시 `contents`에 행이 쌓이고 상한(100/30)을 넘지 않는다
- [ ] 같은 배치를 두 번 돌려도 행이 늘지 않는다 (C-19)
- [ ] `utm_source`만 다른 URL 두 개가 1건으로 합쳐진다 (C-14)
- [ ] arXiv와 Semantic Scholar에서 온 같은 논문이 1건이다 (C-16)
- [ ] 국내 뉴스의 `translation_status`가 `skipped`다 (C-31)
- [ ] 논문 1건에 `translation_jobs`가 최대 4건 생긴다 (C-35)
- [ ] `full_text_original`에 대한 job이 **없다** (C-34)
- [ ] 실행 후 `papers_pdf/`가 비어 있다 (C-28)
- [ ] 한 소스를 일부러 죽여도 나머지가 수집된다 (C-9)
- [ ] `batch_runs.stats`에 소스별 건수와 섹션 추출 성공률이 있다
- [ ] 로그에 API 키가 평문으로 없다

## 9. 보고할 것

```
CHANGED: <파일>
SUMMARY: <3줄 이내>
VERIFY:  <§8 각 항목>
STATS:   <실제 1회 수집 결과 — 소스별 건수, dedup으로 합쳐진 건수,
          섹션 추출 성공률(full/abstract_only/failed 비율)>
CONCERNS: <섹션 추출 실패율이 높으면 반드시 적어라 — PRD-03 R-2와 직결된다>
```

**섹션 추출 성공률이 50% 미만이면 휴리스틱을 더 손대지 말고 그대로 보고하라.**
PRD-03 §5.3의 "3섹션 번역" 결정 자체를 재검토해야 할 신호다.
