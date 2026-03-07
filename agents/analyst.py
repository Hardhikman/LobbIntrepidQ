from google.adk.agents import LlmAgent

from agents.prompt_store import get_agent_instruction


def get_analyst_agent(model, tools):
    return LlmAgent(
        name="Analyst",
        model=model,
        tools=tools,
        instruction=get_agent_instruction("analyst"),
    )
