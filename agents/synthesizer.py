from google.adk.agents import LlmAgent

from agents.prompt_store import get_agent_instruction


def get_synthesizer_agent(model):
    return LlmAgent(
        name="Synthesizer",
        model=model,
        tools=[],
        instruction=get_agent_instruction("synthesizer"),
    )
