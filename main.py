import asyncio
import logging
import os
import uuid
from typing import Tuple

import gradio as gr
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import config
import tools
from agents.analyst import get_analyst_agent
from agents.critic import get_critic_agent
from agents.lobbyist import get_lobbyist_agent
from agents.synthesizer import get_synthesizer_agent


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

session_service = InMemorySessionService()


async def run_agent_step(agent_name: str, agent: LlmAgent, prompt: str, run_id: str) -> Tuple[str, str]:
    """Executes a single agent step within a specific run context."""
    logger.info("Starting Agent: %s [RunID: %s]", agent_name, run_id)

    app_name = "agents"
    session_id = f"sess_{agent_name.lower()}_{run_id}"
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

    try:
        await session_service.create_session(app_name=app_name, user_id="user", session_id=session_id)
    except Exception:
        pass

    msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    final_text = ""

    try:
        async for event in runner.run_async(user_id="user", session_id=session_id, new_message=msg):
            if event.is_final_response() and event.content and event.content.parts:
                text_parts = [p.text for p in event.content.parts if hasattr(p, "text") and p.text]
                final_text = "\n".join(text_parts)
                break

    except Exception as exc:
        error_msg = f"Execution Error in {agent_name}: {str(exc)}"
        logger.error(error_msg)
        return "", error_msg

    if not final_text.strip():
        return "", f"{agent_name} returned empty response."

    return final_text, f"{agent_name} Completed."


async def run_policy_analysis(topic: str, google_key: str) -> str:
    run_id = str(uuid.uuid4())[:8]
    logger.info("--- Starting Analysis Run: %s ---", run_id)

    active_google_key = google_key or getattr(config, "GOOGLE_API_KEY", "")
    if not active_google_key:
        print("\n[!] Authentication Error: Missing Google API Key.")
        print("    Use the 'set_key <your_key>' command to set it.")
        return ""

    os.environ["GOOGLE_API_KEY"] = active_google_key

    try:
        safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
        ]
        model = Gemini(model="gemini-2.5-flash-lite", safety_settings=safety_settings)
    except Exception as exc:
        print(f"\n[!] Setup Failed: {exc}")
        return ""

    print("\n[1/4] Pre-fetching research data...")
    analyst_keywords = tools.extract_skill_keywords("analyst")
    critic_keywords = tools.extract_skill_keywords("critic")

    analyst_data = tools.prefetch_data(topic, analyst_keywords)
    critic_data = tools.prefetch_data(topic, critic_keywords)
    rss_data = tools.prefetch_rss_news(topic)

    print("\n[2/4] Analyst and Critic: analyzing data in parallel...")
    analyst_agent = get_analyst_agent(model)
    critic_agent = get_critic_agent(model)

    results = await asyncio.gather(
        run_agent_step(
            "Analyst",
            analyst_agent,
            f"Topic: {topic}\n\nResearch Data:\n{analyst_data}\n\nAnalyze this data.",
            run_id,
        ),
        run_agent_step(
            "Critic",
            critic_agent,
            f"Topic: {topic}\n\nResearch Data:\n{critic_data}\n\nNews:\n{rss_data}\n\nCritique this topic.",
            run_id,
        ),
    )

    (analyst_res, analyst_log), (critic_res, critic_log) = results

    if "Error" in analyst_log or "Error" in critic_log:
        print("\n[!] Error during Analyst/Critic phase.")
        print(f"Analyst: {analyst_log}")
        print(f"Critic: {critic_log}")
        return ""

    print("\n[3/4] Lobbyist: strategizing directives...")
    lobbyist_agent = get_lobbyist_agent(model)
    lobbyist_prompt = (
        f"Analysis: {analyst_res}\n"
        f"Critique: {critic_res}\n"
        "Propose 3 directives."
    )
    lobbyist_res, lobbyist_log = await run_agent_step("Lobbyist", lobbyist_agent, lobbyist_prompt, run_id)
    if "Error" in lobbyist_log:
        print(f"\n[!] Error during Lobbyist phase: {lobbyist_log}")
        return ""

    print("\n[4/4] Synthesizer: writing final executive summary...")
    summary_agent = get_synthesizer_agent(model)
    summary_prompt = (
        f"Context:\n{analyst_res}\n{critic_res}\n{lobbyist_res}\n"
        "Summarize."
    )
    summary_res, summary_log = await run_agent_step("Synthesizer", summary_agent, summary_prompt, run_id)
    if "Error" in summary_log:
        print(f"\n[!] Error during Synthesizer phase: {summary_log}")
        return ""

    import datetime
    import re as _re

    def _strip_leading_heading(text: str) -> str:
        """Remove any leading markdown heading (e.g., '## Executive Summary: ...') from agent output."""
        return _re.sub(r"^\s*#{1,3}\s+[^\n]*\n*", "", text, count=1).strip()

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_content = (
        f"# Policy Report: {topic}\n"
        f"**Date**: {timestamp}\n\n"
        f"## Executive Summary\n{_strip_leading_heading(summary_res)}\n\n"
        f"## Directives\n{_strip_leading_heading(lobbyist_res)}\n\n"
        f"## Analysis\n{_strip_leading_heading(analyst_res)}\n\n"
        f"## Critique\n{_strip_leading_heading(critic_res)}\n"
    )
    return md_content


def print_help():
    print("\nAvailable commands:")
    print("  run <topic>      - Run the analysis pipeline on the given topic")
    print("  set_key <key>    - Set or update the Google API key for this session")
    print("  help             - Show this help message")
    print("  exit / quit      - Exit the CLI\n")


async def cli_loop():
    banner = (
        '\x1b[94m    __          __    __  \x1b[0m\x1b[38;5;208m  ____      __                  _     ______ \x1b[0m\n' +
        '\x1b[94m   / /   ____  / /_  / /_ \x1b[0m\x1b[38;5;208m /  _/___  / /_________  ____  (_)___/ / __ \\\x1b[0m\n' +
        '\x1b[94m  / /   / __ \\/ __ \\/ __ \\\x1b[0m\x1b[38;5;208m / // __ \\/ __/ ___/ _ \\/ __ \\/ / __  / / / /\x1b[0m\n' +
        '\x1b[94m / /___/ /_/ / /_/ / /_/ /\x1b[0m\x1b[38;5;208m/ // / / / /_/ /  /  __/ /_/ / / /_/ / /_/ / \x1b[0m\n' +
        '\x1b[94m/_____/\\____/_.___/_.___/_\x1b[0m\x1b[38;5;208m__/_/ /_/\\__/_/   \\___/ .___/_/\\__,_/\\___\\_\\ \x1b[0m\n' +
        '\x1b[94m                          \x1b[0m\x1b[38;5;208m                     /_/                     \x1b[0m\n'
    )
    print(banner)
    print("       Data-Driven Policy Analyzer (ADK-Powered)")
    print("========================================================")
    print("Commands:")
    print("  run <topic>      - Analyze a policy topic (e.g. 'run UBI in India')")
    print("  set_key <key>    - Set your Google API key for this session")
    print("  help             - Show detailed help")
    print("  exit             - Quit the application\n")

    session_key = ""

    import re
    import datetime

    while True:
        try:
            user_input = input("popu> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if not user_input:
            continue

        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in ("exit", "quit"):
            print("Exiting...")
            break

        elif command == "help":
            print_help()

        elif command == "set_key":
            if not args:
                print("[!] Please provide a key: set_key <your_api_key>")
            else:
                session_key = args
                print("[✓] API key updated for this session.")

        elif command == "run":
            if not args:
                print("[!] Please provide a topic: run <topic>")
                continue
            
            topic = args
            print(f"\nStarting analysis for: '{topic}'")
            report_content = await run_policy_analysis(topic, session_key)
            
            if report_content:
                safe_topic = re.sub(r'[^a-zA-Z0-9_\-]', '_', topic[:20])
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
                os.makedirs(reports_dir, exist_ok=True)
                filename = os.path.join(reports_dir, f"report_{safe_topic}_{timestamp}.md")
                
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(report_content)
                print(f"\n[✓] Analysis complete! Report saved to: {filename}\n")
            else:
                print("\n[!] Analysis failed or was aborted.\n")

        else:
            print(f"[!] Unknown command: '{command}'. Type 'help' for available commands.")


if __name__ == "__main__":
    # Suppress specific ADK/httpx logging to keep CLI output clean
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google.adk").setLevel(logging.WARNING)
    
    try:
        asyncio.run(cli_loop())
    except KeyboardInterrupt:
        pass
