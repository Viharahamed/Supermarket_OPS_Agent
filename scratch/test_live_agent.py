# scratch/test_live_agent.py
"""Verification script to test Agent behavior with updated system prompt."""

from app.agent.agent import Agent

def test_query():
    agent = Agent()
    print("Building System Prompt...")
    prompt = agent._build_system_prompt()
    print("--- SYSTEM PROMPT SNIPPET ---")
    print(prompt[:500])
    print("\n----------------------------")

if __name__ == "__main__":
    test_query()
