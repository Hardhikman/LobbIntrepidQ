from google.adk.agents import LlmAgent

from tools import load_agent_skill_content


def get_analyst_agent(model):
    return LlmAgent(
        name="Analyst",
        model=model,
        instruction=load_agent_skill_content("analyst"),
    )
