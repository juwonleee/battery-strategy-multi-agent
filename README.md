# Battery Strategy Multi-Agent

LG에너지솔루션과 CATL의 포트폴리오 다각화 전략을 비교 분석하는 Supervisor 기반 멀티에이전트 프로젝트입니다.

## What It Does
- 공식 PDF 문서를 전처리하고 청킹합니다.
- 전처리 코퍼스를 임베딩해 FAISS 검색 인덱스를 만듭니다.
- 시장 분석, LGES 분석, CATL 분석, 비교/SWOT/점수화, 리뷰를 순차 실행합니다.
- 최종 산출물로 Markdown/PDF 보고서와 JSONL 실행 로그를 남깁니다.

## Current Outputs
- Markdown 보고서: [`outputs/report.md`](./outputs/report.md)
- PDF 보고서: [`outputs/report.pdf`](./outputs/report.pdf)
- 실행 로그: [`logs/app.log`](./logs/app.log)

## Quick Start
1. `.env.example`을 복사해 `.env`를 만듭니다.
2. `OPENAI_API_KEY`를 채웁니다.
3. PDF를 `data/raw` 아래에 넣고 [`data/document_manifest.json`](./data/document_manifest.json)을 맞춥니다.
4. 가상환경과 의존성을 준비합니다.
   - `python3 -m venv .venv`
   - `.venv/bin/pip install -r requirements.txt`
5. 전체 워크플로우를 실행합니다.
   - `TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 .venv/bin/python app.py`

## Main Commands
- 전처리
  - `.venv/bin/python -m tools.preprocessing`
- 검색 인덱스 생성
  - `.venv/bin/python -m tools.retrieval`
- 전체 실행
  - `.venv/bin/python app.py`
- 테스트
  - `.venv/bin/pytest -q`

## Key Files
- 설계 문서: [`docs/design.md`](./docs/design.md)
- 운영 runbook: [`docs/runbook.md`](./docs/runbook.md)
- 그래프 실행: [`graph.py`](./graph.py)
- 상태 타입: [`state.py`](./state.py)
- 보고서 export: [`tools/reporting.py`](./tools/reporting.py)
- 실행 진입점: [`app.py`](./app.py)

## Runtime Layout
- `data/raw`: 원본 PDF
- `data/processed`: 전처리 산출물
- `data/index`: FAISS 인덱스
- `outputs`: 최종 Markdown/PDF 보고서
- `logs`: 실행 로그
- `tests`: fixture 기반 테스트

## Workflow
1. Market Research
2. LGES Analysis
3. CATL Analysis
4. Comparison / SWOT / Scorecard
5. Review
6. Report Assembly

## Notes
- `.env`는 Git 추적 대상이 아닙니다.
- `data/raw`, `data/processed`, `data/index`, `outputs`, `logs`는 로컬 실행 산출물 성격이 강합니다.
- 실패 시 가장 먼저 [`logs/app.log`](./logs/app.log) 마지막 줄과 [`docs/runbook.md`](./docs/runbook.md)의 troubleshooting 섹션을 보면 됩니다.
