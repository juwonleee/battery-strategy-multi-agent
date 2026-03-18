# 배터리 시장 전략 분석 설계 노트

이 문서는 [README.md](../README.md)의 아키텍처 설명을 보조하는 설계 근거 문서다. 구현과 제출 관점의 소스 오브 트루스는 README이며, 이 문서는 "왜 이렇게 설계했는가"를 짧게 정리한다.

## 1. Summary

- 패턴: `Supervisor 기반 Multi-Agent`
- 목표: `LGES vs CATL`의 다각화 전략을 동일 비교 축에서 근거 기반으로 평가
- 핵심 원칙: `worker는 fact/evidence packet만 생성`, `Supervisor가 최종 보고서 책임을 진다`
- 출력물: `Markdown`, `HTML`, `PDF`, `JSONL execution log`

## 2. Supervisor Pattern Rationale

이 과제는 검색 결과를 나누는 것보다 아래 항목이 더 중요하다.

- 비교 축을 먼저 고정할 것
- 재시도와 revision target을 한 곳에서 통제할 것
- 최종 보고서 ownership을 분산시키지 않을 것

그래서 Router/Distributor 대신 Supervisor 패턴을 사용했다. 이 저장소에서 Supervisor는 세 가지를 담당한다.

1. `report_blueprint`를 먼저 생성해 worker contract를 고정한다.
2. 상태를 읽고 다음 단계를 선택한다.
3. review 실패 시 정확한 `revision_target`으로만 되돌린다.

## 3. Agent Contract

| Stage | 목적 | 핵심 출력 | 비고 |
|---|---|---|---|
| `supervisor_blueprint` | 비교 축, comparability, worker 질문 세트 정의 | `report_blueprint` | worker 금지 출력도 함께 고정 |
| `market_research` | 시장 기준점과 재사용 가능한 비교 축 추출 | `market_facts`, `market_context` | 최종 보고서 문장 생성 금지 |
| `lges_analysis` | LGES evidence packet 생성 | `lges_facts`, `lges_profile`, `lges_normalized_metrics` | fact extraction only |
| `catl_analysis` | CATL evidence packet 생성 | `catl_facts`, `catl_profile`, `catl_normalized_metrics` | fact extraction only |
| `comparison` | supervisor synthesis용 candidate packet 생성 | `comparison_input_spec`, `synthesis_claims`, `score_criteria`, `metric_comparison_rows` | final judgment 생성 금지 |
| `supervisor_synthesis` | 제출용 핵심 섹션 작성 | `executive_summary`, `selected_comparison_rows`, `reference_only_rows`, `supervisor_swot`, `supervisor_score_rationales`, `final_judgment` | 최종 내용 owner |
| `review` | 최종 제출 계약 감리 | `report_spec`, `review_result`, `review_issues` | `report_spec` 우선 검토 |

중요한 제한은 다음과 같다.

- worker는 `executive_summary`, `final_judgment`, `final_swot prose`, `final score rationale`을 생성하지 않는다.
- `comparison`은 candidate evidence packet까지만 만든다.
- 최종 제출 계약은 `supervisor_synthesis -> review -> reporting` 경로에서만 완성된다.

## 4. State Contract

핵심 상태 필드는 레이어 단위로 관리한다.

### Blueprint Layer

- `report_blueprint`

### Fact Layer

- `market_facts`, `market_context`, `market_context_summary`
- `lges_facts`, `lges_profile`, `lges_normalized_metrics`
- `catl_facts`, `catl_profile`, `catl_normalized_metrics`
- `citation_refs`, `profitability_reported_rows`

### Comparison Layer

- `comparison_input_spec`
- `synthesis_claims`
- `score_criteria`
- `metric_comparison_rows`
- `low_confidence_claims`

### Supervisor-Owned Report Layer

- `selected_comparison_rows`
- `reference_only_rows`
- `chart_selection`
- `executive_summary`
- `company_strategy_summaries`
- `quick_comparison_panel`
- `supervisor_swot`
- `supervisor_score_rationales`
- `final_judgment`
- `implications`
- `limitations`
- `report_spec`

### Review / Governance Layer

- `review_result`
- `review_issues`
- `validation_warnings`
- `schema_retry_count`
- `review_retry_count`
- `current_step`
- `status`
- `last_error`

`review_result.revision_target`는 `market_research | lges_analysis | catl_analysis | comparison | supervisor_synthesis` 중 하나만 허용한다.

## 5. Evidence And Comparison Flow

실제 데이터 흐름은 아래 순서를 따른다.

1. `document_manifest`가 문서 scope와 메타데이터를 고정한다.
2. preprocessing이 chunked corpus와 retrieval asset을 만든다.
3. worker는 scope별 retrieval query를 실행한다.
4. worker output은 자유형 초안이 아니라 `FactExtractionOutput` 계열이다.
5. normalization이 정량 claim을 비교 가능한 metric layer로 변환한다.
6. comparison은 1차 claim catalog만 사용해 synthesis candidate를 만든다.
7. supervisor synthesis가 최종 비교표, score rationale, final judgment를 작성한다.
8. review는 `report_spec`를 중심으로 제출 계약을 검토한다.
9. reporting이 Markdown / HTML / PDF를 조립한다.

여기서 중요한 점은 비교 단계 이후에 새 검색을 하지 않는다는 것이다. 비교 판단은 이미 검증된 claim catalog와 evidence_refs를 기반으로만 생성한다.

## 6. Review And Retry Policy

`agents/supervisor.py`는 review와 schema retry를 모두 통제한다.

- worker 또는 synthesis가 실패하면 같은 단계에서 schema retry를 수행한다.
- review가 실패하면 `revision_target`으로만 되돌린다.
- target 단계 이후 산출물만 비우고, 이전 단계 산출물은 유지한다.
- retry budget을 넘기면 종료하거나 advisory issue를 남긴 채 완료한다.

이 정책 덕분에 "어디가 잘못됐는지"와 "어디부터 다시 해야 하는지"가 분리된다.

## 7. Human-In-The-Loop Extension

현재 기본 경로에는 HITL이 없다. 나중에 넣는다면 위치는 `comparison` 이후 `supervisor_synthesis` 이전으로 고정한다.

- 입력: worker fact packet, normalized metric, comparison candidate evidence
- 사람의 역할: 누락 키워드 보완, 재탐색 지시, 비교 축 보정
- 금지: 최종 보고서 직전 결론 직접 수정

즉, HITL은 `checkpoint input package`를 보강하는 용도여야 하며 최종 output ownership을 바꾸면 안 된다.

## 8. SWOT And Final Implication Decision

SWOT은 회사별 진단으로 유지한다. 다만 보고서 목적은 비교 판단이므로:

- SWOT 생성: 회사별 진단
- 시사점과 종합 판단: `supervisor_synthesis`가 comparative synthesis로 작성

이 분리를 통해 개별 회사 설명은 유지하면서도 최종 결론은 비교 논리 중심으로 묶을 수 있다.

## 9. Reporting Contract

최종 제출 계약은 `ReportSpec`이다. `tools.reporting.build_report_spec`가 supervisor-owned state를 조립하고, `tools.validation.validate_final_delivery_state`가 export gate를 적용한다.

필수 제출 섹션은 다음과 같다.

- `Executive Summary`
- `비교 프레임과 방법`
- `시장 배경`
- `LGES 전략 요약`
- `CATL 전략 요약`
- `Quick Comparison`
- `직접 비교표`
- `참고 지표표`
- `차트와 해석`
- `SWOT`
- `Scorecard`
- `종합 판단`
- `시사점`
- `한계와 주의사항`
- `Reference`

## 10. Testing Implications

테스트는 literal 문장보다 계약을 검증하는 방향이 맞다.

- worker prompt가 forbidden output을 지키는지 확인
- supervisor routing과 revision reset이 정확한지 확인
- report assembly가 필수 섹션을 모두 포함하는지 확인
- acceptance는 특정 문구보다 `section contract + final judgment + references` 존재 여부를 본다

이 방향이 제출 산출물의 안정성과 재현성을 더 잘 보장한다.
