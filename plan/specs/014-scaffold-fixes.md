# SPEC-014: 골격 결함 수정 (보안 · async · CPU)

| 항목 | 값 |
|---|---|
| 근거 | SPEC-002 검증에서 발견된 결함 + 2026-09-23 추가 지시 |
| 목적 | **시크릿 유출을 막고**, 전면 async로 바꾸고, CPU 정책을 반영한다 |
| 선행 조건 | SPEC-002 완료 |
| 성격 | 🔴 **보안 수정 포함.** 이걸 고치기 전에 다음 단계로 가지 않는다 |

## 1. 🔴🔴 결함 1 — 기동 로그에 시크릿이 평문으로 찍힌다

`backend/main.py`, `collector/main.py`, `translator/main.py` **셋 다**:

```python
logger.info("Backend starting", {"config": settings.model_dump()})
```

`shared/logging.py`:
```python
MASK_KEYS = {"password", "passwordhash", "token", "authorization", "cookie", "secret", "apikey", "clientsecret"}
if k.lower() in MASK_KEYS:      # ← 완전 일치만 검사
```

`settings`의 실제 필드는 `db_password`, `jwt_secret`, `naver_client_secret`,
`admin_initial_password`다. **어느 것도 `MASK_KEYS`와 완전 일치하지 않는다.**
→ 세 서비스가 기동할 때마다 **DB 비밀번호와 JWT 서명 키가 로그에 평문으로 남는다.**

PRD-02 FR-14·FR-15 위반이다.

| ID | 요구사항 |
|---|---|
| X-1 | 🔴 `mask_dict`를 **부분 일치**로 바꾼다 — 키 이름에 마스킹 토큰이 **포함되면** 마스킹한다. `db_password`, `jwt_secret`, `naver_client_secret`, `admin_initial_password`가 전부 잡혀야 한다 |
| X-2 | 마스킹 토큰에 `credential`, `passwd`, `pw`, `api_key`, `private_key`, `auth` 를 추가한다 |
| X-3 | 🔴 **세 서비스의 `settings.model_dump()` 로깅을 제거한다.** 꼭 남겨야 하면 **비민감 필드만 화이트리스트**로 골라 찍는다. 전체 덤프를 마스킹에 의존하지 마라 |
| X-4 | `shared/config.py`에 `safe_dump()` 를 두어 마스킹된 설정만 반환하게 하고, 로깅은 이것만 쓴다 |
| X-5 | 🔴 **회귀 테스트를 만든다** — `tests/test_masking.py`. `db_password`·`jwt_secret`·`naver_client_secret`·`admin_initial_password`·중첩 dict·list 안의 값이 마스킹되는지 검증한다 |
| X-6 | 실제로 세 서비스를 기동해 로그에 `secrets/db_password` 파일의 내용이 **나타나지 않는지** 확인한다 |

## 2. 🔴 결함 2 — `db_data`가 named volume이다

`docker-compose.yml`이 최상위 `volumes: db_data:` 를 선언하고 `db_data:/var/lib/postgresql/data`로
마운트한다. 이건 Docker가 관리하는 **named volume**(`mypage_db_data`)이지
저장소의 `./db_data/` 디렉토리가 아니다.

| 증상 |
|---|
| 호스트 `./db_data/`는 **영원히 비어 있다** |
| `.gitignore`의 `db_data/` 항목이 무의미해진다 |
| SPEC-002 §10 "`docker compose down` 후 `db_data/`가 남아 있다"가 통과하지 못한다 |
| 백업·이관 시 볼륨 위치를 따로 찾아야 한다 |

| ID | 요구사항 |
|---|---|
| X-7 | `./db_data:/var/lib/postgresql/data` **bind mount**로 바꾼다 |
| X-8 | 최상위 `volumes:` 선언에서 `db_data`를 제거한다 |
| X-9 | `docker compose config` 로 `type: bind`, `source: /home/infosec/mypage/db_data` 인지 확인한다 |

## 3. 🔴 결함 3 — 전면 async 미반영

SPEC-002 위임 **이후** 사용자가 지시했다: **"모든 시스템은 async로"**.
현재 코드는 전부 동기다 (`psycopg2-binary`, `async def` 0건).

`architecture.md` §7.1.1을 따른다.

| ID | 요구사항 |
|---|---|
| X-10 | `backend`의 모든 엔드포인트를 `async def`로 바꾼다 |
| X-11 | `shared/db.py`를 **`create_async_engine` + `async_sessionmaker` + `AsyncSession`** 으로 바꾼다 |
| X-12 | `psycopg2-binary`를 제거하고 **`asyncpg`** 를 쓴다. DB URL은 `postgresql+asyncpg://` |
| X-13 | `collector`의 스케줄러를 **`AsyncIOScheduler`** 로 바꾸고 `asyncio.run`으로 루프를 띄운다 |
| X-14 | `collector` 의존성에 **`httpx`** 를 넣는다. `requests`를 넣지 마라 |
| X-15 | `/health`가 async로 DB 연결을 확인한다 |
| X-16 | ⚠️ **PyTorch 추론은 동기로 둔다** (architecture.md A-7). `translator`는 큐 I/O만 async로 한다. 억지 async 추론을 만들지 마라 |

## 4. CPU 정책 반영 (architecture.md §4.5)

SPEC-002 위임 이후 추가된 지시다 — **"번역 외에 업무에서 CPU를 최대로 활용"**.

### 4.1 PostgreSQL 튜닝

| ID | 요구사항 |
|---|---|
| X-17 | `db/postgresql.conf` 를 만들고 Compose에서 마운트한다. **이미지에 굽지 마라** |
| X-18 | 값은 architecture.md §4.5.4 표 그대로 — `shared_buffers=32GB`, `effective_cache_size=80GB`, `work_mem=256MB`, `maintenance_work_mem=4GB`, `max_worker_processes=16`, `max_parallel_workers=8`, `max_parallel_workers_per_gather=4`, `max_parallel_maintenance_workers=4`, `random_page_cost=1.1` |
| X-19 | Compose `db` 서비스에 `command: postgres -c config_file=/etc/postgresql/postgresql.conf` 를 준다 |
| X-20 | `shm_size`를 최소 **1gb**로 준다 (병렬 워커가 공유 메모리를 쓴다) |

### 4.2 translator NUMA 바인딩

| ID | 요구사항 |
|---|---|
| X-21 | `translator` 서비스에 `cpuset: "0-3,8-11"` (GPU 0,1 기준)을 주고, 4워커 배치 주석을 단다 |
| X-22 | `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2` 환경변수를 준다 |

### 4.3 수집 병렬

| ID | 요구사항 |
|---|---|
| X-23 | `.env.example`에 `COLLECTOR_WORKERS=8` 을 추가한다 (물리 코어 수) |
| X-24 | `shared/config.py`에 해당 설정을 읽는 필드를 둔다. **풀 구현은 SPEC-004의 몫이다** |

### 4.4 빌드 병렬

| ID | 요구사항 |
|---|---|
| X-25 | `Dockerfile.db`의 `pg_bigm` 컴파일에 `make -j$(nproc)` 를 쓴다 |

## 5. 결함 4 — 시크릿 파일 누락이 조용히 통과한다

`naver_client_secret_file`·`admin_initial_password_file`이 가리키는 파일이 없으면
에러 없이 빈 문자열로 넘어간다. `db_password`·`jwt_secret`은 올바르게 실패한다.

| ID | 요구사항 |
|---|---|
| X-26 | **경로가 지정됐는데 파일이 없으면** 넷 다 `FileNotFoundError`로 실패한다 |
| X-27 | 단 **파일이 존재하고 내용이 비어 있는 것**은 허용한다 — 외부 API 키는 아직 안 받았을 수 있다 (`init-secrets.sh`가 빈 파일로 만든다). 이 경우 경고 로그만 남긴다 |

## 6. 🔴 하드 제약

| 제약 | 내용 |
|---|---|
| 빌드 금지 | 🔴 **`docker compose build` / `up` / `curl` 을 실행하지 마라.** CUDA 이미지 수 GB 다운로드와 `pg_bigm` 컴파일로 수십 분이 걸려 agy가 죽는다. SPEC-002에서 실제로 exit 90이 났다. **검증은 `docker compose config`, `python -m py_compile`, `bash -n`, `pytest tests/` 까지만** |
| 범위 | 수집·번역·검색 로직, DB 스키마를 만들지 마라. 여전히 "빈 껍데기"다 |
| `benchmarks/` | 건드리지 마라. 다른 작업이 돌고 있다 |
| CUDA 태그 | `nvidia/cuda:12.1.1-*` 유지. 올리지 마라 |
| 시크릿 | 실제 비밀값을 코드·설정·테스트·주석에 쓰지 마라. 테스트는 더미값을 쓴다 |
| `.gitignore` | 기존 항목을 지우지 마라 |

## 7. 검증 방법

- [ ] `pytest tests/test_masking.py` 통과 — `db_password`·`jwt_secret`·`naver_client_secret`·`admin_initial_password`가 전부 마스킹된다
- [ ] 중첩 dict와 list 안의 값도 마스킹된다
- [ ] 세 서비스 `main.py` 에 `settings.model_dump()` 직접 로깅이 **없다**
- [ ] `grep -rn "model_dump()" backend/ collector/ translator/` 가 비어 있거나 `safe_dump` 경유다
- [ ] `docker compose config` 에서 `db_data`가 `type: bind` 다
- [ ] 최상위 `volumes:` 에 `db_data` 선언이 없다
- [ ] `grep -rn "psycopg2\|requests" backend/ collector/ shared/ *.txt` 가 비어 있다
- [ ] `asyncpg`, `create_async_engine`, `AsyncSession`, `AsyncIOScheduler`, `httpx` 가 있다
- [ ] `backend/main.py` 의 엔드포인트가 전부 `async def` 다
- [ ] `translator`는 추론이 동기다 (억지 async 아님)
- [ ] `db/postgresql.conf` 가 있고 Compose가 마운트한다. §4.1의 9개 값이 전부 있다
- [ ] `translator` 에 `cpuset` 과 `OMP_NUM_THREADS=2` 가 있다
- [ ] `Dockerfile.db` 에 `make -j$(nproc)` 가 있다
- [ ] `.env.example` 에 `COLLECTOR_WORKERS=8` 이 있다
- [ ] 시크릿 파일 경로가 지정됐는데 없으면 넷 다 실패한다
- [ ] 빈 파일은 경고만 남기고 통과한다
- [ ] `python -m py_compile` 전체 통과
- [ ] `git status --short` 에 `secrets/` 가 없다

## 8. 보고할 것

```
CHANGED: <파일>
SUMMARY: <3줄 이내>
SECURITY: <마스킹 테스트 결과. db_password/jwt_secret이 실제로 마스킹되는지.
           model_dump 로깅 제거 여부>
ASYNC:   <asyncpg/AsyncSession/AsyncIOScheduler/httpx 적용 여부, psycopg2·requests 잔존 여부>
CPU:     <postgresql.conf 9개 값, cpuset, OMP_NUM_THREADS, make -j>
VOLUME:  <docker compose config 의 db_data 타입>
VERIFY:  <§7 각 항목>
CONCERNS: <없으면 none>
```

🔴 **마스킹 테스트가 통과하지 못하면 고쳤다고 보고하지 마라.** 시크릿 유출이 이 수정의 핵심이다.
