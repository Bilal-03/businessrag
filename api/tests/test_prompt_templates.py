from src.prompts.prompt_templates import build_agent_prompt


def test_prompt_requests_english_output():
    prompt = build_agent_prompt("General Agent")

    assert "Write the final answer in English." in prompt
