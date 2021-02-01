from argparse import ArgumentParser
import sys

from aws_jumpcloud import commands
from aws_jumpcloud.version import __VERSION__

DESCRIPTION = "A vault for securely storing and accessing AWS credentials in development environments."


def main():
    parser = _build_parser()
    args = parser.parse_args()
    if "func" not in args:
        parser.print_usage()
        print("error: the following arguments are required: command")
        sys.exit(2)
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("")


def _build_parser():
    parser = ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        "--version", action="version", version="%(prog)s (" + __VERSION__ + ")"
    )
    subparsers = parser.add_subparsers(dest="command")
    _add_help_command(subparsers)
    _add_info_command(subparsers)
    _add_list_command(subparsers)
    _add_add_command(subparsers)
    _add_remove_command(subparsers)
    _add_exec_command(subparsers)
    _add_export_command(subparsers)
    _add_rotate_command(subparsers)
    _add_is_active_command(subparsers)
    return parser


def _add_help_command(p):
    parser_help = p.add_parser("help", help="show this help message and exit")
    parser_help.set_defaults(func=_print_help)


def _add_info_command(p):
    parser_info = p.add_parser("info", help="display info about your JumpCloud account")
    parser_info.set_defaults(func=commands.get_info)


def _add_list_command(p):
    parser_list = p.add_parser("list", help="list profiles and their sessions")
    parser_list.set_defaults(func=commands.list_profiles)


def _add_add_command(p):
    parser_add = p.add_parser("add", help="add a new profile")
    parser_add.add_argument("profile", help="name of the profile")
    parser_add.add_argument("url", help="JumpCloud SSO URL for this profile", nargs="?")
    parser_add.add_argument(
        "-r",
        "--role",
        help="IAM role to assume after login (name or ARN)",
        dest="role_to_assume",
        metavar="ROLE",
    )
    parser_add.add_argument(
        "--external-id",
        help="External ID to provide when assuming a role after login",
        metavar="ID",
    )
    parser_add.set_defaults(func=commands.add_profile)


def _add_remove_command(p):
    parser_remove = p.add_parser(
        "remove", help="remove a profile and any temporary IAM sessions"
    )
    parser_remove_mx = parser_remove.add_mutually_exclusive_group(required=True)
    parser_remove_mx.add_argument("profile", help="name of the profile", nargs="?")
    parser_remove_mx.add_argument(
        "--all",
        action="store_true",
        help="revoke all temporary IAM sessions and deletes stored JumpCloud authentication information.",
    )
    parser_remove.set_defaults(func=commands.remove_profile)


def _add_exec_command(p):
    parser_exec = p.add_parser(
        "exec", help="executes a command with AWS credentials in the environment"
    )
    parser_exec.add_argument("profile", help="name of the profile")
    parser_exec.add_argument("command", nargs="+")
    parser_exec.set_defaults(func=commands.exec_command)


def _add_is_active_command(p):
    parser_export = p.add_parser(
        "is-active", help="returns 1 if a session is active for this profile"
    )
    parser_export.add_argument("profile", help="name of the profile")
    parser_export.set_defaults(func=commands.is_active)


def _add_export_command(p):
    parser_export = p.add_parser(
        "export",
        help="show export statements to load AWS credentials into your environment",
    )
    parser_export.add_argument("profile", help="name of the profile")
    parser_export.set_defaults(func=commands.export_vars)


def _add_rotate_command(p):
    parser_rotate = p.add_parser(
        "rotate",
        help="rotates the IAM session (generates new temporary credentials) for an existing profile",
    )
    parser_rotate_mx = parser_rotate.add_mutually_exclusive_group(required=True)
    parser_rotate_mx.add_argument("profile", help="name of the profile", nargs="?")
    parser_rotate_mx.add_argument(
        "--all",
        action="store_true",
        help="generate new temporary IAM credentials for all existing profiles",
    )
    parser_rotate.set_defaults(func=commands.rotate_session)


def _print_help(args):
    _build_parser().print_help()
