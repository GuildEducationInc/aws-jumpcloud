from argparse import ArgumentParser
from datetime import datetime
import getpass
import os
import sys
import subprocess
from subprocess import PIPE

from aws_jumpcloud.aws import AWSCredentials, assume_role_with_saml
from aws_jumpcloud.jumpcloud import JumpCloudSession
from aws_jumpcloud.keyring import Keyring
from aws_jumpcloud.profile import Profile
from aws_jumpcloud.saml import get_assertion_roles

DESCRIPTION = "A vault for securely storing and accessing AWS credentials in development environments."


def main():
    parser = _build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("")


def _build_parser():
    parser = ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--debug", action="store_true", help="Show debugging output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_list = subparsers.add_parser("list", help="List profiles and their sessions")
    parser_list.set_defaults(func=_list_profiles)

    parser_add = subparsers.add_parser("add", help="Adds a new profile")
    parser_add.add_argument("profile", help="Name of the profile")
    parser_add.set_defaults(func=_add_profile)

    parser_remove = subparsers.add_parser("remove", help="Removes a profile and any sessions")
    parser_remove.add_argument("profile", help="Name of the profile")
    parser_remove.set_defaults(func=_remove_profile)

    parser_exec = subparsers.add_parser(
        "exec", help="Executes a command with AWS credentials in the environment")
    parser_exec.add_argument("profile", help="Name of the profile")
    parser_exec.add_argument("command", nargs="+")
    parser_exec.set_defaults(func=_exec)

    parser_rotate = subparsers.add_parser("rotate", help="Rotates credentials for an existing profile")
    parser_rotate.add_argument("profile", help="Name of the profile")
    parser_rotate.set_defaults(func=_rotate_credentials)

    return parser


def _list_profiles(args):
    keyring = Keyring()
    profiles = keyring.get_all_profiles()
    credentials = keyring.get_all_credentials()
    output = []
    for profile in keyring.get_all_profiles():
        if profile.name in credentials:
            expires_at = credentials[profile.name].expires_at.astimezone().strftime("%c %Z")
        else:
            expires_at = "<no active credentials>"
        output.append([profile.name, profile.aws_account_id, profile.aws_role,
                       profile.default_region, expires_at])
    _print_columns(["Profile", "AWS Account ID", "AWS Role", "AWS Region",
                    "Temporary credentials valid until"], output)


def _print_columns(headers, rows):
    sizes = []
    for value in headers:
        sizes.append(len(value))
    for row in rows:
        for i, value in enumerate(row):
            sizes[i] = max(sizes[i], len(value) + 2)

    for size, value in zip(sizes, headers):
        sys.stdout.write(value.ljust(size + 2))
    sys.stdout.write("\n")
    for size in sizes:
        sys.stdout.write("=" * size)
        sys.stdout.write("  ")
    sys.stdout.write("\n")
    sys.stdout.flush()
    for row in rows:
        for size, value in zip(sizes, row):
            sys.stdout.write(value.ljust(size + 2))
        sys.stdout.write("\n")
        sys.stdout.flush()


def _add_profile(args):
    keyring = Keyring()
    if keyring.get_profile(args.profile):
        print(f"Error: Profile {args.profile} already exists.")
        print("If you want to change the profile defaults, remove the profile and add it again.")
        sys.exit(1)

    aws_account_id = input(f"Enter the AWS account ID for {args.profile}: ").strip()
    aws_role = input(f"Enter the IAM role to assume for {args.profile}: ").strip()
    default_region = input(f"Choose a default AWS region [us-west-2]: ").strip() or "us-west-2"
    keyring.store_profile(Profile(args.profile, aws_account_id, aws_role, default_region))
    print(f"Profile {args.profile} added.")


def _remove_profile(args):
    keyring = Keyring()
    if not keyring.get_profile(args.profile):
        print(f"Profile {args.profile} not found, nothing to do.")
        sys.exit(0)

    has_credentials = not not keyring.get_credentials(args.profile)
    keyring.delete_credentials(args.profile)
    keyring.delete_profile(args.profile)
    if has_credentials:
        print(f"Profile {args.profile} and temporary credentials removed.")
    else:
        print(f"Profile {args.profile} removed.")


def _exec(args):
    keyring = Keyring()
    profile = keyring.get_profile(args.profile)
    if not profile:
        print(f"Error: Profile {args.profile} not found; you must add it first.")
        sys.exit(1)
    creds = keyring.get_credentials(args.profile)
    if not creds:
        _login(keyring, profile)
        creds = keyring.get_credentials(args.profile)

    env = {'AWS_ACCESS_KEY_ID': creds.access_key_id,
           'AWS_SECRET_ACCESS_KEY': creds.secret_access_key,
           'AWS_SECURITY_TOKEN': creds.session_token,
           'AWS_SESSION_TOKEN': creds.session_token,
           'AWS_DEFAULT_REGION': profile.default_region,
           'AWS_REGION': profile.default_region}

    # run the command given on the command line
    print("running command")
    result = subprocess.run(args.command, env=env)
    print(f"exiting with status code {result.returncode}")
    sys.exit(result.returncode)


def _rotate_credentials(args):
    keyring = Keyring()
    profile = keyring.get_profile(args.profile)
    if not profile:
        print(f"Error: Profile {args.profile} not found.")
        sys.exit(1)

    keyring.delete_credentials(args.profile)
    print(f"Credentials for {args.profile} removed.")
    _login(keyring, profile)
    creds = keyring.get_credentials(args.profile)

    print(f"AWS temporary credentials rotated; new credentials valid until {creds.expires_at.strftime('%c %Z')}.")


def _login(keyring, profile):
    email, password = keyring.get_jumpcloud_login()
    dirty = False
    if email and password:
        print("Using JumpCloud login details from your OS keychain.")
    if not email or not password:
        email = input("Enter your JumpCloud email address: ").strip()
        password = getpass.getpass("Enter your JumpCloud password: ").strip()
        keyring.store_jumpcloud_login(email, password)
        print("JumpCloud login details saved in your OS keychain.")

    session = JumpCloudSession(email, password)
    session.login()
    # TODO handle various exceptions

    saml_assertion = session.get_aws_saml_assertion()
    roles = get_assertion_roles(saml_assertion)
    assert(len(roles) == 1)
    role = roles[0]  # TODO make this work with more than one role in the assertion

    creds = assume_role_with_saml(role, saml_assertion)
    keyring.store_credentials(profile.name, creds)
    return creds
