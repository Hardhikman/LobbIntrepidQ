from google.adk.agents import LlmAgent

from tools import load_agent_skill_content


def get_critic_agent(model):
    return LlmAgent(
        name="Critic",
        model=model,
        instruction=load_agent_skill_content("critic"),
    )
