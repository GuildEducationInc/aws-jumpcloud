from argparse import ArgumentParser
import getpass
import sys
import subprocess
from subprocess import PIPE

from aws_jumpcloud.aws import assume_role_with_saml, get_account_alias, parse_arn
from aws_jumpcloud.jumpcloud import JumpCloudSession, JumpCloudError, JumpCloudAuthFailure
from aws_jumpcloud.jumpcloud import JumpCloudServerError, JumpCloudUnexpectedResponse
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
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_help = subparsers.add_parser("help", help="Show this help message and exit")
    parser_help.set_defaults(func=_help)

    parser_info = subparsers.add_parser("info", help="Display info about your JumpCloud account")
    parser_info.set_defaults(func=_get_info)

    parser_list = subparsers.add_parser("list", help="List profiles and their sessions")
    parser_list.set_defaults(func=_list_profiles)

    parser_add = subparsers.add_parser("add", help="Add a new profile")
    parser_add.add_argument("profile", help="name of the profile")
    parser_add.set_defaults(func=_add_profile)

    parser_remove = subparsers.add_parser("remove", help="Remove a profile and any temporary IAM sessions")
    parser_remove_mx = parser_remove.add_mutually_exclusive_group(required=True)
    parser_remove_mx.add_argument("profile", help="name of the profile", nargs="?")
    parser_remove_mx.add_argument(
        "--all", action="store_true",
        help="revoke all temporary IAM sessions and deletes stored JumpCloud authentication information.")
    parser_remove.set_defaults(func=_remove_profile)

    parser_exec = subparsers.add_parser(
        "exec", help="Executes a command with AWS credentials in the environment")
    parser_exec.add_argument("profile", help="name of the profile")
    parser_exec.add_argument("command", nargs="+")
    parser_exec.set_defaults(func=_exec_command)

    parser_rotate = subparsers.add_parser(
        "rotate", help="Rotates temporary IAM session for an existing profile")
    parser_rotate.add_argument("profile", help="name of the profile")
    parser_rotate.set_defaults(func=_rotate_session)

    return parser


def _help(args):
    _build_parser().print_help()


def _get_info(args):
    keyring = Keyring()
    print("")
    email = keyring.get_jumpcloud_email()
    password = keyring.get_jumpcloud_password()
    ts = keyring.get_jumpcloud_timestamp()
    print(f"JumpCloud email: {email or '<not stored>'}")
    print(f"JumpCloud password: {'******** (hidden)' if password else '<not stored>'}")
    print(f"Last JumpCloud authentication: {ts.astimezone().strftime('%c %Z') if ts else '<never>'}")


def _list_profiles(args):
    keyring = Keyring()
    profiles = keyring.get_all_profiles()
    if len(profiles) == 0:
        print("")
        print("No profiles found. Use \"aws-jumpcloud add <profile>\" to store a new profile.")
        sys.exit(0)
    sessions = keyring.get_all_sessions()
    output = []
    for profile in sorted(profiles.values(), key=lambda p: p.name):
        aws_account_desc = profile.aws_account_alias or profile.aws_account_id or "<unknown>"
        aws_role = profile.aws_role or "<unknown>"
        if profile.name in sessions:
            expires_at = sessions[profile.name].expires_at.astimezone().strftime("%c %Z")
        else:
            expires_at = "<no active session>"
        output.append([profile.name, aws_account_desc, aws_role, expires_at])
    print("")
    _print_columns(["Profile", "AWS Account", "AWS Role", "IAM session expires"], output)


def _print_columns(headers, rows):
    sizes = []
    for value in headers:
        sizes.append(len(value))
    for row in rows:
        for i, value in enumerate(row):
            sizes[i] = max(sizes[i], len(value) + 2)

    print("".join([value.ljust(size + 2) for size, value in zip(sizes, headers)]))
    print("  ".join(["=" * size for size in sizes]))
    for row in rows:
        print("".join([value.ljust(size + 2) for size, value in zip(sizes, row)]))


def _add_profile(args):
    keyring = Keyring()
    if keyring.get_profile(args.profile):
        print(f"Error: Profile {args.profile} already exists.")
        print("If you want to change the profile defaults, remove the profile and add it again.")
        sys.exit(1)

    jumpcloud_url = input(f"Enter the JumpCloud SSO URL for {args.profile}: ").strip()
    if not jumpcloud_url.startswith("https://sso.jumpcloud.com/saml2/"):
        print("Error: Not a valid JumpCloud SSO URL, must start with https://sso.jumpcloud.com/saml2/.")
        sys.exit(1)
    profile = Profile(args.profile, jumpcloud_url)
    keyring.store_profile(profile)
    print(f"Profile {args.profile} added.")


def _remove_profile(args):
    keyring = Keyring()

    if args.all:
        keyring.delete_all_data()
        print("")
        print("All configuration profiles, temporary IAM sessions, and JumpCloud login")
        print("credentials have been removed from your OS keychain.")
    elif keyring.get_profile(args.profile):
        has_session = not not keyring.get_session(args.profile)
        keyring.delete_session(args.profile)
        keyring.delete_profile(args.profile)
        if has_session:
            print(f"Profile {args.profile} and temporary IAM session removed.")
        else:
            print(f"Profile {args.profile} removed.")
    else:
        print(f"Profile {args.profile} not found, nothing to do.")


def _exec_command(args):
    keyring = Keyring()
    profile = keyring.get_profile(args.profile)
    if not profile:
        print(f"Error: Profile {args.profile} not found; you must add it first.")
        sys.exit(1)
    session = keyring.get_session(args.profile)
    if not session:
        _login(keyring, profile)
        session = keyring.get_session(args.profile)
        print("")

    # Find the full path to the program that the user wants to run, otherwise
    # subprocess.run() won't be able to find it. (I'm not sure exactly why this
    # happens -- it looks like subprocess.run() can find programs in /usr/bin
    # but not /usr/local/bin?)
    result = subprocess.run(["which", args.command[0]], stdout=PIPE)
    if result.returncode == 0 and len(result.stdout.strip()) > 0:
        args.command[0] = result.stdout.strip()
    elif result.returncode == 1:
        print(f"{args.command[0]}: command not found")
        sys.exit(127)
    else:
        sys.stdout.write(result.stdout)
        sys.exit(result.returncode)

    # Run the command that the user wanted, with AWS credentials in the environment
    env = {'AWS_ACCESS_KEY_ID': session.access_key_id,
           'AWS_SECRET_ACCESS_KEY': session.secret_access_key,
           'AWS_SECURITY_TOKEN': session.session_token,
           'AWS_SESSION_TOKEN': session.session_token}
    result = subprocess.run(args.command, env=env)
    sys.exit(result.returncode)


def _rotate_session(args):
    keyring = Keyring()
    profile = keyring.get_profile(args.profile)
    if not profile:
        print(f"Error: Profile {args.profile} not found.")
        sys.exit(1)

    keyring.delete_session(args.profile)
    print(f"Temporary IAM session for {args.profile} removed.")

    _login(keyring, profile)
    session = keyring.get_session(args.profile)
    print(f"AWS temporary session rotated; new session valid until {session.expires_at.strftime('%c %Z')}.")


def _login(keyring, profile):
    email = keyring.get_jumpcloud_email()
    password = keyring.get_jumpcloud_password()
    if email and password:
        print("Using JumpCloud login details from your OS keychain.")
    else:
        email = input("Enter your JumpCloud email address: ").strip()
        password = getpass.getpass("Enter your JumpCloud password: ").strip()
        keyring.store_jumpcloud_email(email)
        keyring.store_jumpcloud_password(password)
        print("JumpCloud login details saved in your OS keychain.")

    session = JumpCloudSession(email, password)
    try:
        session.login()
    except JumpCloudError as e:
        print(f"\nError: {e.message}")
        if isinstance(e, JumpCloudAuthFailure):
            keyring.store_jumpcloud_email(None)
            keyring.store_jumpcloud_password(None)
            print("- You will be prompted for your username and password the next time you try.")
        elif isinstance(e, JumpCloudServerError):
            error_msg = e.jumpcloud_error_message or e.response.text
            print(f"- JumpCloud error message: {error_msg}")
        elif isinstance(e, JumpCloudUnexpectedResponse):
            print(f"- JumpCloud response body: {e.response.text}")
        sys.exit(1)

    print("Attempting SSO authentication to Amazon Web Services...")
    saml_assertion = session.get_aws_saml_assertion(profile)
    roles = get_assertion_roles(saml_assertion)

    # Warning: It's a valid JumpCloud configuration to present more than one
    # role in the assertion, but we don't use that feature right now. We
    # should handle that situation properly at some point.
    assert(len(roles) == 1)
    role = roles[0]

    # Update the AWS account ID and role name if they've changed
    r = parse_arn(role.role_arn)
    if profile.aws_account_id != r.aws_account_id:
        profile.aws_account_id = r.aws_account_id
        keyring.store_profile(profile)
    if profile.aws_role != r.aws_role:
        profile.aws_role = r.aws_role
        keyring.store_profile(profile)

    session = assume_role_with_saml(role, saml_assertion)
    keyring.store_session(profile.name, session)

    # Update the AWS account alias on each login
    alias = get_account_alias(session)
    if alias != profile.aws_account_alias:
        profile.aws_account_alias = alias
        keyring.store_profile(profile)

    print("")
    return session
