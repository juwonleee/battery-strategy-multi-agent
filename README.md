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
3. 필요하면 모델명, 재시도 횟수, 출력 경로를 수정합니다.

기본 디렉터리 구조는 실행 시 자동으로 보장됩니다.
- `data/raw`: 원본 PDF
- `data/processed`: 전처리 산출물
- `data/index`: FAISS 인덱스
- `outputs`: Markdown/PDF 보고서
- `logs`: 실행 로그

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
