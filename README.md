# Popu Agent - Data-Driven Policy Analyzer

Popu Agent is a multi-agent policy analysis system built with Google ADK and Gemini.

## Overview

The app runs four specialized agents in sequence:

1. Analyst: 360-degree policy analysis with data points.
2. Critic: downside/risk analysis and failed examples.
3. Lobbyist: three actionable policy directives.
4. Synthesizer: executive summary with verdict, data, risks, and roadmap.

## Architecture

```mermaid
graph LR
    User([User Input]) --> Analyst[Policy Analyst]
    User --> Critic[Policy Critic]

    Analyst --> Lobbyist[Policy Lobbyist]
    Critic --> Lobbyist

    Analyst --> Synth[Policy Synthesizer]
    Critic --> Synth
    Lobbyist --> Synth

    Synth --> Report([Final Report])
```

## Agent Instructions (SKILL.md)

Agent system prompts and search behaviors are defined via SKILL.md files:

- `skills/agent-skills/analyst/SKILL.md`
- `skills/agent-skills/critic/SKILL.md`
- `skills/agent-skills/lobbyist/SKILL.md`
- `skills/agent-skills/synthesizer/SKILL.md`

To change agent behavior, output formatting, or data-fetching keywords, edit the corresponding `SKILL.md` file.

## Installation

This project targets Python 3.11+.

Install dependencies:

```bash
pip install -r requirements.txt
```

*(Note: The `gradio` dependency has been removed in favor of a fast, native CLI.)*

## API Keys

Create `.env` in project root:

```env
GOOGLE_API_KEY=your_google_api_key_here
```

## Running the App

Launch the interactive CLI:

```bash
python main.py
```

If your default Python does not have dependencies installed:

```bash
.\popu_agent_env\Scripts\python.exe main.py
```

### CLI Commands

Once inside the `popu>` prompt, you can use:
- `run <topic>` — Runs the 4-phase analysis pipeline on your requested topic.
- `set_key <key>` — Sets or overrides the Google API key for the current session.
- `help` — Shows available commands.
- `exit` — Quits the CLI.

## Project Structure

- `main.py`: App orchestration and interactive CLI loop.
- `config.py`: Runtime configuration and environment reads.
- `tools.py`: Tool integrations (DDGS search, RSS fetch, keyword extraction).
- `agents/*.py`: Agent factory files that load instructions from SKILL.md.
- `skills/agent-skills/*/SKILL.md`: The single source of truth for agent system prompts and keywords.

## Workflow

1. **Pre-fetch**: System extracts keywords from SKILL.md and fetches research via DuckDuckGo and RSS.
2. **Analysis**: Analyst and Critic run in parallel using the pre-fetched data context.
3. **Strategy**: Lobbyist uses Analyst + Critic outputs to synthesize directives.
4. **Summary**: Synthesizer condenses all outputs into an executive summary.
5. **Output**: The final Markdown report is automatically saved to your current directory (e.g. `report_Topic_Name_20261201.md`).
