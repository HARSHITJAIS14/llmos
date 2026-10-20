"""
LLM_OS CLI Entry Point.

Usage:
    python -m llm_os "Open Calendar and add chest day at 3pm"
    python -m llm_os --app Calendar "Add an event for team standup at 4pm"
    python -m llm_os --model gpt-4o --max-steps 30 "Open VS Code to the LLM_OS project"

Environment Variables:
    OPENAI_API_KEY      - Your OpenAI API key (required if not using Groq)
    GROQ_API_KEY        - Your Groq API key (alternative to OpenAI)
    OPENAI_BASE_URL     - Custom base URL (optional, for proxies/alternative providers)
    LLM_OS_MODEL        - Model name (default: gpt-4o or llama-3.1-70b-versatile for Groq)
    AGENT_DESKTOP_BIN   - Path to agent-desktop binary
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        prog='llm-os',
        description='LLM OS — Agentic AI layer for OS-level computer use automation',
    )
    parser.add_argument(
        'task',
        type=str,
        help='Natural language task instruction (e.g., "Open Calendar and add chest day at 3pm")',
    )
    parser.add_argument(
        '--app',
        type=str,
        default=None,
        help='Target application name hint (e.g., Calendar, Notion, "Visual Studio Code")',
    )
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='LLM model name (default: gpt-4o, or set LLM_OS_MODEL env var)',
    )
    parser.add_argument(
        '--max-steps',
        type=int,
        default=20,
        help='Maximum step budget (default: 20)',
    )
    parser.add_argument(
        '--log-dir',
        type=str,
        default=None,
        help='Directory for execution logs (default: ATree_tool/tasks/logs/)',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose debug logging',
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    # Set model via env var if provided as argument
    if args.model:
        os.environ['LLM_OS_MODEL'] = args.model

    # Validate API key
    if not os.environ.get('OPENAI_API_KEY') and not os.environ.get('GROQ_API_KEY') and not os.environ.get('ANTHROPIC_API_KEY'):
        print('❌ Error: OPENAI_API_KEY, GROQ_API_KEY, or ANTHROPIC_API_KEY environment variable is not set.')
        print('   Set it with: export OPENAI_API_KEY="sk-..." or export ANTHROPIC_API_KEY="sk-ant-..."')
        sys.exit(1)

    # Import here to avoid circular imports and allow env vars to be set first
    from llm_os.orchestrator import run_task

    # Run the task
    final_state = run_task(
        task=args.task,
        app_name=args.app,
        max_steps=args.max_steps,
        log_dir=args.log_dir,
    )

    # Exit code based on status
    status = final_state.get('status', 'unknown')
    sys.exit(0 if status == 'done' else 1)


if __name__ == '__main__':
    main()
