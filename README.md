# Battery Strategy Multi-Agent

LG Energy Solution vs CATL portfolio diversification strategy analysis using a supervisor-based multi-agent workflow.

## Overview
- Objective: Compare LG Energy Solution and CATL under the EV downturn and derive evidence-based strategic insights.
- Method: Agentic RAG with company-separated analysis paths, structured comparison, and review.
- Tools: LangGraph, LangChain, Python, FAISS, multilingual-e5-large

## Features
- Market context analysis from curated official documents
- Separate analysis paths for LG Energy Solution and CATL
- Structured comparison, SWOT, and evidence-based scorecard
- Bias-aware validation using limited web verification
- Evidence traceability for key claims and conclusions

## Tech Stack

| Category | Details |
|---|---|
| Framework | LangGraph, LangChain, Python |
| Retrieval | FAISS |
| Embedding | intfloat/multilingual-e5-large |
| Pattern | Supervisor-based Multi-Agent Workflow |
| Output | Markdown report, PDF export |

## Agents
- Supervisor Agent: Controls routing and retry decisions
- Market Research Agent: Summarizes market context
- LGES Analysis Agent: Analyzes LG Energy Solution strategy
- CATL Analysis Agent: Analyzes CATL strategy
- Comparison Agent: Builds comparison matrix, SWOT, and scorecard
- Review Agent: Checks evidence quality, consistency, and bias

## Architecture
See [docs/design.md](./docs/design.md).

## Directory Structure
```text
.
├── README.md
└── docs
    └── design.md
```

## Contributors
- 양정우: Agent design, workflow design, report structure
