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
    elif args.command == "chat":
        from zoe.cli import cmd_chat
        return cmd_chat()
    else:
        print_banner()
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
