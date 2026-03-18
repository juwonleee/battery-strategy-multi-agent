# Operator Runbook

## Purpose
이 문서는 배터리 전략 비교 분석 워크플로우를 로컬에서 재현하고, 실패 시 어디를 먼저 확인해야 하는지 빠르게 찾기 위한 운영용 문서입니다.

## Prerequisites
- Python 3.13 또는 호환 버전
- `.venv` 가상환경
- 유효한 `OPENAI_API_KEY`
- `data/raw` 아래에 준비된 PDF 원본
- `data/document_manifest.json`에 실제 파일명과 페이지 범위 반영

## First-Time Setup
1. 가상환경 생성
   - `python3 -m venv .venv`
2. 의존성 설치
   - `.venv/bin/pip install -r requirements.txt`
   - `.venv/bin/python -m playwright install chromium`
3. 환경변수 준비
   - `.env.example`을 복사해 `.env` 생성
   - `OPENAI_API_KEY` 입력
4. 원본 PDF 배치
   - `data/raw/*.pdf`
5. manifest 확인
   - `data/document_manifest.json`

## Normal Run
1. 전처리만 확인
   - `.venv/bin/python -m tools.preprocessing`
2. 검색 인덱스만 확인
   - `.venv/bin/python -m tools.retrieval`
3. 전체 워크플로우 실행
   - `TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 .venv/bin/python app.py`

## Expected Outputs
- Markdown 보고서
  - `outputs/report.md`
- HTML 보고서
  - `outputs/report.html`
- PDF 보고서
  - `outputs/report.pdf`
- 실행 로그
  - `logs/app.log`
- 전처리 코퍼스
  - `data/processed/corpus.jsonl`
- 검색 인덱스
  - `data/index/faiss.index`

## Sample Outputs In This Workspace
- 최신 샘플 Markdown
  - `outputs/report.md`
- 최신 샘플 HTML
  - `outputs/report.html`
- 최신 샘플 PDF
  - `outputs/report.pdf`
- 최신 실행 로그
  - `logs/app.log`

## Validation Commands
- 문법 검증
  - `.venv/bin/python -m py_compile app.py graph.py state.py agents/*.py tools/*.py`
- 테스트
  - `.venv/bin/pytest -q`

## Acceptance Suite
- schema tests
  - `tests/test_schema_contracts.py`
- normalization tests
  - `tests/test_normalization.py`
- validator and review gate tests
  - `tests/test_validation.py`
  - `tests/test_review_prompt.py`
- report assembly and PDF smoke tests
  - `tests/test_reporting.py`
- chart spec tests
  - `tests/test_charting.py`
- workflow and export E2E
  - `tests/test_app_e2e.py`
  - `tests/test_acceptance_suite.py`

## Manual Submission Checklist
- `Supervisor Blueprint -> Workers -> Supervisor Synthesis -> Review -> Export` 순서가 로그에 보이는지 확인
- worker 출력이 최종 요약/최종 판단 문장을 직접 담고 있지 않은지 확인
- 최종 보고서의 Summary, SWOT, Scorecard, 종합 판단이 supervisor-owned fields에서 렌더링되는지 확인
- 회색 면이나 장식용 배경이 본문 가독성을 해치지 않는지 확인
- 표지 이후 본문 페이지에 큰 공백만 남는 페이지가 없는지 확인
- 표가 페이지 경계에서 잘려도 읽을 수 있게 유지되는지 확인
- 단일 시점 차트에 `Trend`라는 제목이 남아 있지 않은지 확인
- 직접 비교 불가 지표가 본표가 아니라 `참고 지표표`에 있는지 확인
- `종합 판단` 섹션이 결론 흐름을 마무리하고 `Reference`가 별도 부록처럼 끝나는지 확인
- citation, score rationale, final judgment가 서로 같은 근거를 가리키는지 확인

## Troubleshooting
### `invalid_api_key` 또는 `401`
- `.env`의 `OPENAI_API_KEY`가 유효한지 확인
- 셸에 오래된 키가 export 되어 있지 않은지 확인
- 새 키 발급 후 `.env`만 갱신하고 다시 실행

### `Document manifest not found` 또는 PDF 파일 누락
- `data/document_manifest.json` 경로 확인
- `source_path`가 실제 `data/raw` 파일명과 일치하는지 확인

### `Page X is out of bounds`
- manifest의 `page_range`가 PDF 실제 페이지 기준인지 확인
- 발췌본 PDF를 넣었다면 원본 설계 문서 페이지가 아니라 발췌본의 실제 페이지 번호를 써야 함

### Retrieval assets missing
- `.venv/bin/python -m tools.preprocessing`
- `.venv/bin/python -m tools.retrieval`

### Comparison 또는 review 단계에서 재시도 후 실패
- `logs/app.log` 마지막 줄 확인
- 근거 없는 비교행이나 scorecard evidence 누락이 원인인지 확인
- 필요하면 해당 문서의 페이지 범위 확대 또는 manifest 보완

### PDF export skipped
- `playwright` 설치 여부 확인
- `.venv/bin/pip install -r requirements.txt`
- `.venv/bin/python -m playwright install chromium`
- Markdown/HTML 산출물은 `outputs/report.md`, `outputs/report.html`에 남아 있어야 함

## Operational Notes
- `.env`, `data/raw`, `data/processed`, `data/index`, `outputs`, `logs`는 로컬 실행 산출물 성격이 강하므로 Git에 올리지 않는 운영이 기본입니다.
- 실행 로그는 JSONL 형식이라 마지막 몇 줄만 봐도 어느 단계에서 멈췄는지 판단 가능합니다.
- 비교 단계가 가장 무거워서 실행 시간이 길 수 있습니다.
