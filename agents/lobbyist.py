from google.adk.agents import LlmAgent

from agents.prompt_store import get_agent_instruction


def get_lobbyist_agent(model, tools):
    return LlmAgent(
        name="Lobbyist",
        model=model,
        tools=tools,
        instruction=get_agent_instruction("lobbyist"),
    )
