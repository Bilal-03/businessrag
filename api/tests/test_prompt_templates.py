from src.prompts.prompt_templates import build_agent_prompt


def test_hindi_prompt_requires_devanagari_output():
    prompt = build_agent_prompt("General Agent", language="hi")

    assert "entirely in Hindi using Devanagari" in prompt
    assert "Do not answer in English" in prompt


def test_default_prompt_requests_english_output():
    prompt = build_agent_prompt("General Agent")

    assert "Write the final answer in English." in prompt
