import json

from prompts import build_comparison_prompt
from state import CompanyClaimCatalog, ComparisonInputClaim, ComparisonInputSpec


def test_build_comparison_prompt_instructs_model_to_omit_claim_id(sample_state):
    input_spec = ComparisonInputSpec(
        lges_catalog=CompanyClaimCatalog(
            owner_scope="lges",
            claims=[
                ComparisonInputClaim(
                    claim_id="lges-diversification_strategy-1",
                    scope="lges",
                    category="diversification_strategy",
                    claim_text="LGES는 ESS를 확대한다.",
                    key_value=None,
                    source_label="LGES Deck",
                    page_locator="p.7",
                )
            ],
        ),
        catl_catalog=CompanyClaimCatalog(
            owner_scope="catl",
            claims=[
                ComparisonInputClaim(
                    claim_id="catl-diversification_strategy-1",
                    scope="catl",
                    category="diversification_strategy",
                    claim_text="CATL은 EV와 ESS를 함께 확장한다.",
                    key_value=None,
                    source_label="CATL Prospectus",
                    page_locator="p.46",
                )
            ],
        ),
    )

    prompt = build_comparison_prompt(
        goal=sample_state["goal"],
        comparison_input_spec=input_spec,
    )
    payload = json.loads(prompt.input_text)

    assert "comparison_input_spec" in payload
    assert "claim_id 필드를 직접 쓰지 말고 생략한다" in prompt.instructions
