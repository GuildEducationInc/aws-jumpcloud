from argparse import ArgumentParser
import sys

from aws_jumpcloud import commands
from aws_jumpcloud.version import __VERSION__

DESCRIPTION = "A vault for securely storing and accessing AWS credentials in development environments."


def main():
    parser = _build_parser()
    args = parser.parse_args()
    if 'func' not in args:
        parser.print_usage()
        print("error: the following arguments are required: command")
        sys.exit(2)
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("")


def _build_parser():
    parser = ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--version", action='version', version="%(prog)s ("+__VERSION__+")")

    subparsers = parser.add_subparsers(dest="command")

    parser_help = subparsers.add_parser("help", help="show this help message and exit")
    parser_help.set_defaults(func=_print_help)

    parser_info = subparsers.add_parser("info", help="display info about your JumpCloud account")
    parser_info.set_defaults(func=commands.get_info)

    parser_list = subparsers.add_parser("list", help="list profiles and their sessions")
    parser_list.set_defaults(func=commands.list_profiles)

    parser_add = subparsers.add_parser("add", help="add a new profile")
    parser_add.add_argument("profile", help="name of the profile")
    parser_add.set_defaults(func=commands.add_profile)

    parser_remove = subparsers.add_parser("remove", help="remove a profile and any temporary IAM sessions")
    parser_remove_mx = parser_remove.add_mutually_exclusive_group(required=True)
    parser_remove_mx.add_argument("profile", help="name of the profile", nargs="?")
    parser_remove_mx.add_argument(
        "--all", action="store_true",
        help="revoke all temporary IAM sessions and deletes stored JumpCloud authentication information.")
    parser_remove.set_defaults(func=commands.remove_profile)

    parser_exec = subparsers.add_parser(
        "exec", help="executes a command with AWS credentials in the environment")
    parser_exec.add_argument("profile", help="name of the profile")
    parser_exec.add_argument("command", nargs="+")
    parser_exec.set_defaults(func=commands.exec_command)

    parser_rotate = subparsers.add_parser(
        "rotate",
        help="rotates the IAM session (generates new temporary credentials) for an existing profile")
    parser_rotate_mx = parser_rotate.add_mutually_exclusive_group(required=True)
    parser_rotate_mx.add_argument("profile", help="name of the profile", nargs="?")
    parser_rotate_mx.add_argument(
        "--all", action="store_true",
        help="generate new temporary IAM credentials for all existing profiles")
    parser_rotate.set_defaults(func=commands.rotate_session)

    return parser


def _print_help(args):
    _build_parser().print_help()
