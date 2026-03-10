from google.adk.agents import LlmAgent

from tools import load_agent_skill_content


def get_lobbyist_agent(model):
    return LlmAgent(
        name="Lobbyist",
        model=model,
        instruction=load_agent_skill_content("lobbyist"),
    )
