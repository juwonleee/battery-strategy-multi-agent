# Battery Strategy Multi-Agent

LG에너지솔루션과 CATL의 포트폴리오 다각화 전략을 비교 분석하기 위한 Supervisor 기반 멀티에이전트 프로젝트입니다.

## Overview
- Objective: EV 캐즘 환경에서 LG에너지솔루션과 CATL의 전략 차이를 근거 기반으로 비교 분석
- Method: Agentic RAG, 기업별 분석 경로 분리, 구조화 출력, 비교/검토 단계 분리
- Tools: LangGraph, LangChain, Python, FAISS, multilingual-e5-large

## Features
- 공식 문서 기반 시장 배경 분석
- LGES / CATL 분리 분석으로 문맥 오염 방지
- 비교표, SWOT, scorecard 생성
- 편향 보정 및 교차 검증 중심의 제한적 웹 검증
- 핵심 주장별 근거 추적

## Tech Stack

| Category | Details |
|---|---|
| Framework | LangGraph, LangChain, Python |
| Retrieval | FAISS |
| Embedding | intfloat/multilingual-e5-large |
| Pattern | Supervisor-based Multi-Agent Workflow |
| Output | Markdown 보고서, PDF 변환 |

## Agents
- Supervisor Agent: 흐름 제어, 재시도 판단, 다음 단계 라우팅
- Market Research Agent: 시장 배경 요약
- LGES Analysis Agent: LG에너지솔루션 전략 분석
- CATL Analysis Agent: CATL 전략 분석
- Comparison Agent: 비교표, SWOT, scorecard 생성
- Review Agent: 근거성, 일관성, 편향 검토

## Architecture
- 설계 문서: [docs/design.md](./docs/design.md)
- 그래프 정의: [graph.py](./graph.py)
- 상태 정의: [state.py](./state.py)
- 런타임 설정: [config.py](./config.py)

## Runtime Setup
1. `.env.example`을 복사해 `.env`를 생성합니다.
2. `OPENAI_API_KEY`를 채웁니다.
3. 분석에 사용할 PDF를 `data/raw` 아래에 넣습니다.
4. [`data/document_manifest.json`](./data/document_manifest.json)을 채웁니다.
5. 필요하면 모델명, 전처리 청크 크기, 재시도 횟수, 출력 경로를 수정합니다.

기본 디렉터리 구조는 실행 시 자동으로 보장됩니다.
- `data/raw`: 원본 PDF
- `data/processed`: 전처리 산출물
- `data/index`: FAISS 인덱스
- `outputs`: Markdown/PDF 보고서
- `logs`: 실행 로그

## Document Manifest
manifest는 JSON 배열이며, 각 항목은 아래 필드를 사용합니다.

- `document_id`: 문서 고유 식별자
- `title`: 보고서/자료명
- `source_path`: PDF 경로. 보통 `data/raw/<file>.pdf`
- `source_type`: `company_report`, `industry_report`, `regulatory_filing`, `speech`, `presentation`, `other`
- `company_scope`: `market`, `lges`, `catl`, `shared`
- `published_at`: 선택. `YYYY-MM-DD`
- `page_range`: 선택. `10-18,134-146` 형식

예시는 [`data/document_manifest.example.json`](./data/document_manifest.example.json)에 있습니다.

## Preprocessing
- `python3 -m tools.preprocessing`: manifest를 읽고 PDF를 청킹해 `data/processed`에 저장
- `python3 -m tools.retrieval`: 청크 코퍼스를 임베딩하고 `data/index`에 FAISS 인덱스와 메타데이터 저장
- `python3 app.py`: 전처리 후 전체 워크플로우 실행

## Retrieval
- 전역 FAISS 인덱스 1개를 만들고, 조회 시 `market`, `lges`, `catl`, `cross_check` scope로 필터링합니다.
- 인덱스 산출물은 `data/index/faiss.index`, `data/index/faiss_metadata.jsonl`입니다.
- 기본 임베딩 모델은 `intfloat/multilingual-e5-large`이며, 질의/문서 prefix를 자동 적용합니다.

## Directory Structure
```text
.
├── README.md
├── app.py
├── graph.py
├── state.py
├── requirements.txt
├── agents
│   ├── __init__.py
│   ├── supervisor.py
│   ├── market_research.py
│   ├── lges_analysis.py
│   ├── catl_analysis.py
│   ├── comparison.py
│   └── review.py
├── data
├── docs
│   └── design.md
├── outputs
├── prompts
│   └── __init__.py
└── tools
    └── __init__.py
```

## Contributors
- 양정우: Agent 설계, 워크플로우 설계, 보고서 구조 설계
