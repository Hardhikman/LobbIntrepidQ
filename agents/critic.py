from google.adk.agents import LlmAgent

from agents.prompt_store import get_agent_instruction


def get_critic_agent(model, tools):
    return LlmAgent(
        name="Critic",
        model=model,
        tools=tools,
        instruction=get_agent_instruction("critic"),
    )
