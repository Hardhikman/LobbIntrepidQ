from google.adk.agents import LlmAgent

from tools import load_agent_skill_content


def get_synthesizer_agent(model):
    return LlmAgent(
        name="Synthesizer",
        model=model,
        instruction=load_agent_skill_content("synthesizer"),
    )
