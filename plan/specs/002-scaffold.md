# SPEC-002: 프로젝트 골격 (Compose · DB 이미지 · 공용 패키지)

| 항목 | 값 |
|---|---|
| 근거 | roadmap.md 단계 0 (0.2~0.5), architecture.md §7 |
| 목적 | 서비스 6종이 **기동되고 서로 연결되는 것까지만** 만든다. 기능 구현은 하지 않는다 |
| 선행 조건 | 없음 (SPEC-001 벤치마크와 병행 가능) |
| 후행 | SPEC-003 데이터 계층 (단계 2) |

## 1. 이 명세의 범위 — "골격"의 정의

**동작하는 빈 껍데기를 만든다.** 각 서비스가 기동해서 헬스체크에 응답하고,
서로 네트워크로 닿고, DB에 접속되는 것까지가 완료 조건이다.

| 만든다 | 만들지 않는다 |
|---|---|
| `docker-compose.yml` 6서비스 | 수집 로직, 번역 로직, 검색 질의 |
| `Dockerfile.db` (PG16 + `pg_bigm`) | DB 테이블·스키마 (→ SPEC-003) |
| `shared/` 패키지 (설정·DB 세션·로깅) | SQLAlchemy 모델 (→ SPEC-003) |
| `backend/` FastAPI 진입점 + `/health` | 실제 API 엔드포인트 |
| `collector/`·`translator/` 진입점 | 스케줄러 잡, GPU 추론 |
| `Caddyfile` | TLS 인증서 |
| `secrets/` 생성 스크립트 | 실제 외부 API 키 (사람이 넣는다) |

## 2. 🔴 절대 건드리지 말 것

- **`benchmarks/` 디렉토리** — SPEC-001이 동시에 작업 중이다. 읽지도 쓰지도 마라
- **`plan/` 아래 전부** — 기획 문서다
- **`.claude/`, `CLAUDE.md`, `tools/`** — 워크플로 설정이다
- **`frontend/package.json`, `frontend/vite.config.js`** — 이미 있다. 이 명세에서 고치지 않는다
- **GPU를 점유하는 작업** — 벤치마크가 GPU 0·1을 쓰고 있다. `translator` 컨테이너를
  **기동 테스트하지 마라.** 빌드까지만 하고 실행은 하지 않는다

## 3. 환경 (실측)

| 항목 | 값 |
|---|---|
| Docker | 29.1.3 |
| Compose | v2.40.3 (플러그인 방식 — `docker compose`) |
| GPU 노출 | **CDI 방식** — `docker info`에 `nvidia.com/gpu=0` ~ `=7`로 보인다 |
| 실행 계정 | `docker` 그룹 소속. `sudo` 불필요 |
| 호스트 CUDA | 12.1 / cuDNN 9.10.2 (**고정**) |

## 4. `docker-compose.yml`

`architecture.md` §7.6의 6서비스.

| 서비스 | 이미지 | 포트 | 비고 |
|---|---|---|---|
| `proxy` | `caddy:2-alpine` | `${PROXY_PORT}:80` | `/api/*`→backend, `/*`→frontend |
| `frontend` | `node:20-slim` | — (proxy 경유) | Vite 개발 서버, 볼륨 마운트 |
| `backend` | 빌드 (`python:3.11-slim`) | — | FastAPI + uvicorn |
| `db` | 빌드 (`Dockerfile.db`) | — | PG16 + `pg_bigm` |
| `collector` | `backend`와 **같은 이미지** | — | 진입점만 다르다 |
| `translator` | 빌드 (CUDA 베이스) | — | `profiles: [batch]` — 기본 기동 안 함 |

### 4.1 요구사항

| ID | 요구사항 |
|---|---|
| S-1 | `docker compose up -d`로 `proxy`·`frontend`·`backend`·`db`·`collector` 5종이 뜬다 |
| S-2 | `translator`는 `profiles: ["batch"]`로 묶어 **기본 `up`에서 제외**한다 (PRD-03 FR-43 "배치 시각에만 기동") |
| S-3 | `db`는 `db_data/`를 볼륨 마운트하고 healthcheck(`pg_isready`)를 둔다 |
| S-4 | `backend`는 `db` healthy 이후 기동한다 (`depends_on.condition: service_healthy`) |
| S-5 | `backend`·`collector`는 같은 이미지를 쓰고 `command`로만 갈라진다 |
| S-6 | 모든 서비스가 `secubrief` 이름의 사용자 정의 네트워크에 붙는다 |
| S-7 | `.env`를 읽어 포트·배치 설정을 주입한다. **민감값은 `.env`에 두지 않는다** |

### 4.2 시크릿 (PRD-02 §3)

| ID | 요구사항 |
|---|---|
| S-8 | Compose 최상위 `secrets:` 블록에 파일 기반 시크릿 4종을 선언한다 — `db_password`, `jwt_secret`, `naver_client_secret`, `admin_initial_password` |
| S-9 | 각 서비스에 필요한 것만 `secrets:`로 마운트한다 |
| S-10 | **민감값을 `environment:`로 넘기지 마라** (PRD-02 FR-2 — `docker inspect`에 노출된다). `*_FILE` 경로만 넘긴다 |
| S-11 | `tools/init-secrets.sh`를 만든다 — `secrets/` 디렉토리와 4개 파일을 생성하고, `db_password`·`jwt_secret`은 랜덤 생성, 외부 API 키는 빈 파일로 두고 안내를 출력한다. 권한 `0600` |
| S-12 | 이미 있는 시크릿 파일은 덮어쓰지 않는다 |

### 4.3 GPU (`translator`)

`docker info`가 CDI를 노출하므로 **CDI 장치명을 쓴다.**

```yaml
translator:
  profiles: ["batch"]
  devices:
    - nvidia.com/gpu=0
    - nvidia.com/gpu=1
```

| ID | 요구사항 |
|---|---|
| S-13 | GPU는 CDI 장치명(`nvidia.com/gpu=N`)으로 할당한다 |
| S-14 | 워커 4개가 각각 GPU 2장을 쓰는 구성임을 **주석으로 명시**한다 (0+1 / 2+3 / 4+5 / 6+7). 실제 4개 서비스 정의는 SPEC-004에서 한다 — 지금은 `translator` 1개만 예시로 둔다 |
| S-15 | NUMA 그룹(0~3 / 4~7) 경계를 넘는 짝을 쓰지 말라는 주석을 남긴다 |

## 5. `Dockerfile.db` — PostgreSQL 16 + `pg_bigm`

`pg_bigm`은 기본 `postgres` 이미지에 없다. 소스에서 빌드해야 한다.

| ID | 요구사항 |
|---|---|
| S-16 | `postgres:16` 기반으로 `pg_bigm`을 빌드해 설치한다 |
| S-17 | 멀티스테이지로 빌드 도구(`build-essential`, `postgresql-server-dev-16`)를 최종 이미지에 남기지 않는다 |
| S-18 | `docker-entrypoint-initdb.d/`에 `CREATE EXTENSION IF NOT EXISTS pg_bigm;`을 넣어 최초 기동 시 활성화한다 |
| S-19 | 기본 인코딩 `UTF8`, locale `C.UTF-8` |
| S-20 | 빌드 성공 후 `SELECT * FROM pg_extension WHERE extname='pg_bigm';`으로 확인 가능해야 한다 |

> `pg_bigm` 최신 릴리스는 PostgreSQL 16을 지원한다. 버전은 빌드 시점 최신 안정판을 쓰되,
> **Dockerfile에 버전을 고정**하고 주석으로 남겨라.

## 6. `shared/` 공용 패키지

`backend`·`collector`·`translator` 셋이 공유한다 (architecture.md A-1).

```
shared/
├── __init__.py
├── config.py      설정 로드 — .env + *_FILE 시크릿 읽기
├── db.py          SQLAlchemy 엔진·세션 (모델은 SPEC-003)
└── logging.py     구조화 JSON 로그 + 마스킹
```

| ID | 요구사항 |
|---|---|
| S-21 | `config.py`는 Pydantic Settings로 `.env`를 읽고, `*_FILE` 환경변수가 있으면 **그 파일 내용을 값으로 읽는다** (PRD-02 FR-3) |
| S-22 | 시크릿 파일이 없으면 기동 시 명확한 에러로 실패한다 (조용히 빈 값으로 넘어가지 말 것) |
| S-23 | `db.py`는 SQLAlchemy 2.0 스타일 엔진·세션 팩토리만 제공한다. 모델 정의 금지 |
| S-24 | `logging.py`는 JSON 로그를 표준출력으로 낸다 |
| S-25 | **로그 마스킹** (PRD-02 FR-14·FR-15) — 직렬화 전 키 이름으로 마스킹. 대상: `password`, `passwordHash`, `token`, `authorization`, `cookie`, `secret`, `apiKey`, `clientSecret` |
| S-26 | 이메일은 `a***@example.com` 형태로 부분 마스킹한다 (FR-16) |

## 7. 각 서비스 진입점

| ID | 요구사항 |
|---|---|
| S-27 | `backend/main.py` — FastAPI 앱, `GET /health`가 DB 연결을 확인하고 `{"status":"ok","db":"ok"}`를 반환한다 |
| S-28 | `collector/main.py` — APScheduler를 띄우고 `.env`의 `BATCH_TIMES`(기본 `09:00,21:00`)에 **로그만 남기는 빈 잡**을 등록한다 |
| S-29 | `translator/main.py` — 인자 파싱과 GPU 가시성 확인까지만. **모델을 로드하지 않는다** |
| S-30 | 셋 다 `shared/`를 import해서 설정·로깅이 실제로 동작함을 보인다 |
| S-31 | `requirements.txt`를 `backend`용(FastAPI 계열)과 `translator`용(PyTorch 계열)으로 **나눈다** |

## 8. `Caddyfile`

| ID | 요구사항 |
|---|---|
| S-32 | `/api/*` → `backend:8000`, 그 외 → `frontend:3000` |
| S-33 | 개발 환경 기준으로 평문 HTTP(:80). TLS는 두지 않는다 |
| S-34 | 단일 오리진이므로 **backend에 CORS 설정을 넣지 않는다** |

## 9. 🔴 하드 제약

| 제약 | 내용 |
|---|---|
| CUDA 버전 | `translator` 베이스는 **`nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04`**. 13.x는 Pascal 지원이 삭제돼 GPU 8장이 전부 죽는다. 태그를 올리지 마라 |
| 시크릿 | 실제 비밀값을 **코드·Compose·`.env`·주석 어디에도 쓰지 마라**. 랜덤 생성은 `init-secrets.sh`에서만 |
| `.gitignore` | `secrets/`, `.env`, `db_data/`는 이미 제외돼 있다. **이 설정을 건드리지 마라** |
| 기존 파일 | `.env.example`, `.gitignore`, `frontend/*`는 이미 있다. 필요하면 **추가**하되 기존 항목을 지우지 마라 |
| `translator` 실행 | 빌드만 하고 **기동하지 마라** (§2, GPU 점유 중) |

## 10. 검증 방법 (완료 판정)

- [ ] `bash tools/init-secrets.sh` 실행 시 `secrets/` 4개 파일이 `0600`으로 생긴다
- [ ] 두 번째 실행에서 기존 파일을 덮어쓰지 않는다
- [ ] `docker compose build` 가 `db`·`backend`·`translator` 전부 성공한다
- [ ] `docker compose up -d` 로 5개 서비스가 뜬다 (`translator` 제외)
- [ ] `docker compose ps` 에서 `db`가 `healthy`
- [ ] `curl localhost/api/health` 가 `{"status":"ok","db":"ok"}` 를 반환한다 (proxy 경유)
- [ ] `docker compose exec db psql -U <user> -d <db> -c "SELECT extname FROM pg_extension WHERE extname='pg_bigm';"` 가 1행을 반환한다
- [ ] `docker compose exec backend env | grep -iE "password|secret|token"` 에 **평문 비밀값이 안 보인다** (`*_FILE` 경로만 보여야 한다)
- [ ] `docker compose logs collector` 에 스케줄 등록 로그가 보인다
- [ ] `git status --short` 에 `secrets/` 가 나타나지 않는다
- [ ] `docker compose down` 후 `db_data/` 가 남아 있다

## 11. 보고할 것

```
CHANGED: <생성·수정한 파일>
SUMMARY: <구현 요약 3줄 이내>
VERIFY:  <§10 체크리스트 각 항목의 통과/실패>
CONCERNS: <확신 없는 지점. 없으면 none>
```

`pg_bigm` 빌드가 실패하면 **우회하지 말고 실패를 보고하라.** 검색 전체가 이 확장에 걸려 있어
대체 경로를 임의로 선택하면 안 된다.
