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

    args = parser.parse_args()

    if args.command == "check-permissions":
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
    else:
        print_banner()
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
