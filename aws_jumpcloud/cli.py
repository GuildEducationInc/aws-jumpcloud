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

JUMPCLOUD_KEYCHAIN_NAME = "aws-jumpcloud"
AWS_KEYCHAIN_NAME = "aws-jumpcloud temporary credentials"


def main():
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)

    # email = os.environ.get("JUMPCLOUD_EMAIL") or input("Enter your JumpCloud email address: ")
    # password = get_password(email)

    # j = JumpCloudSession(email, password)
    # j.login()

    # saml_assertion_xml = j.get_aws_saml_assertion()
    # roles = get_assertion_roles(saml_assertion_xml)
    # if len(roles) > 1:
    #     print("Please select a role to assume:")
    #     for i, role in enumerate(roles):
    #         print(f"   {i + 1}. {role.role_arn}")
    #     choice = input("Role: ")
    #     role = roles[int(choice) - 1]
    # else:
    #     role = roles[0]

    # creds = assume_role_with_saml(role, saml_assertion_xml)
    # print("")
    # print(f"# Credentials for {role.role_arn} (expires at {creds.expires_at.strftime('%c %Z')})")
    # print(f"export AWS_ACCESS_KEY_ID={creds.access_key_id}")
    # print(f"export AWS_SECRET_ACCESS_KEY={creds.secret_access_key}")
    # print(f"export AWS_SESSION_TOKEN={creds.session_token}")
    # print("")
    # print(creds.dumps())


# def get_password(email):
#     password = keyring.get_password(JUMPCLOUD_KEYCHAIN_NAME, email)
#     if password:
#         print("Found your JumpCloud password in your macOS keychain.")
#     else:
#         password = getpass.getpass("Enter your JumpCloud password: ").strip()
#         if len(password) == 0:
#             return None
#         resp = input("Would you like to store this in your macOS keychain [yes/no]? ")
#         if resp.lower() == 'yes':
#             keyring.set_password(JUMPCLOUD_KEYCHAIN_NAME, email, password)
#     print("")
#     return password

DESCRIPTION = "A vault for securely storing and accessing AWS credentials in development environments."


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
            expires_at = credentials[profile.name].expires_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        else:
            expires_at = "<no active credentials>"
        output.append([profile.name, profile.aws_account_id, profile.aws_role,
                       profile.default_region, expires_at])
    _print_columns(["Profile", "AWS Account ID", "AWS Role", "AWS Region",
                    "Temporary credentials expire at"], output)


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

    aws_account_id = input("AWS account ID: ").strip()
    aws_role = input("AWS role: ").strip()
    default_region = input("Default AWS region [us-west-2]: ").strip() or "us-west-2"
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

    print("")
    print(f"# Credentials for {profile.role_arn} (expires at {creds.expires_at.strftime('%c %Z')})")
    print(f"export AWS_ACCESS_KEY_ID={creds.access_key_id}")
    print(f"export AWS_SECRET_ACCESS_KEY={creds.secret_access_key}")
    print(f"export AWS_SESSION_TOKEN={creds.session_token}")
    print(f"export AWS_SECURITY_TOKEN={creds.session_token}")
    print(f"export AWS_DEFAULT_REGION={profile.default_region}")
    print(f"export AWS_REGION={profile.default_region}")
    print("")


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
