"""Main entrypoint for Zoe CLI."""

import argparse
import sys
from zoe.cli import (
    cmd_check_permissions,
    cmd_list_tools,
    cmd_interactive,
    run_acceptance_suite,
    print_banner,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Zoe — Personal Local AI Computer Assistant for macOS (Phase 1)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    subparsers.add_parser("start", help="Launch the unified Zoe local assistant runtime (Voice + Vision + Notch + Memory)")
    subparsers.add_parser("check-permissions", help="Verify macOS Accessibility and Screen Recording permissions")
    subparsers.add_parser("test-all", help="Execute the 21-point automated acceptance suite")
    subparsers.add_parser("interactive", help="Start interactive computer control CLI")
    subparsers.add_parser("list-tools", help="List all registered computer control tools and descriptions")
    subparsers.add_parser("model-status", help="Check local LLM connection, status, and privacy configuration")
    subparsers.add_parser("vision-status", help="Check local vision model connection, status, and privacy configuration")
    subparsers.add_parser("vision-test", help="Test local screen capture and visual UI inspection")
    subparsers.add_parser("voice-status", help="Check local voice subsystem status (Wake Word, STT, TTS, Mic, Notch)")
    subparsers.add_parser("voice-test", help="Run comprehensive local voice subsystem diagnostic")
    subparsers.add_parser("notch-test", help="Visually test MacBook Notch glow animation states")
    subparsers.add_parser("listen", help="Start continuous local voice assistant with ambient Notch UI")
    subparsers.add_parser("chat", help="Start Zoe AI voice/text interactive assistant chat")
    subparsers.add_parser("memory-status", help="Check local persistent memory status")
    subparsers.add_parser("memory-list", help="List all stored user and task memories")
    mem_search_p = subparsers.add_parser("memory-search", help="Search stored memories by keyword")
    mem_search_p.add_argument("query", help="Keyword to search")
    mem_del_p = subparsers.add_parser("memory-delete", help="Delete a stored memory by key")
    mem_del_p.add_argument("key", help="Key to remove")
    mem_clr_p = subparsers.add_parser("memory-clear", help="Clear all stored memories")
    mem_clr_p.add_argument("--force", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    if args.command == "start":
        from zoe.runtime import get_runtime
        get_runtime().start()
        return 0
    elif args.command == "check-permissions":
        return cmd_check_permissions()
    elif args.command == "test-all":
        results = run_acceptance_suite()
        return 0 if results["failed"] == 0 else 1
    elif args.command == "interactive":
        return cmd_interactive()
    elif args.command == "list-tools":
        return cmd_list_tools()
    elif args.command == "model-status":
        from zoe.cli import cmd_model_status
        return cmd_model_status()
    elif args.command == "vision-status":
        from zoe.cli import cmd_vision_status
        return cmd_vision_status()
    elif args.command == "vision-test":
        from zoe.cli import cmd_vision_test
        return cmd_vision_test()
    elif args.command == "voice-status":
        from zoe.cli import cmd_voice_status
        return cmd_voice_status()
    elif args.command == "voice-test":
        from zoe.cli import cmd_voice_test
        return cmd_voice_test()
    elif args.command == "notch-test":
        from zoe.cli import cmd_notch_test
        return cmd_notch_test()
    elif args.command == "listen":
        from zoe.cli import cmd_listen
        return cmd_listen()
    elif args.command == "chat":
        from zoe.cli import cmd_chat
        return cmd_chat()
    elif args.command == "memory-status":
        from zoe.cli import cmd_memory_status
        return cmd_memory_status()
    elif args.command == "memory-list":
        from zoe.cli import cmd_memory_list
        return cmd_memory_list()
    elif args.command == "memory-search":
        from zoe.cli import cmd_memory_search
        return cmd_memory_search(args.query)
    elif args.command == "memory-delete":
        from zoe.cli import cmd_memory_delete
        return cmd_memory_delete(args.key)
    elif args.command == "memory-clear":
        from zoe.cli import cmd_memory_clear
        return cmd_memory_clear(force=args.force)
    else:
        print_banner()
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
