from argparse import ArgumentParser
import getpass
import os
import sys
import subprocess
from subprocess import PIPE

from aws_jumpcloud.aws import assume_role_with_saml, get_account_alias, parse_arn
from aws_jumpcloud.jumpcloud import JumpCloudSession, JumpCloudError, JumpCloudAuthFailure
from aws_jumpcloud.jumpcloud import JumpCloudMFARequired, JumpCloudServerError, JumpCloudUnexpectedResponse
from aws_jumpcloud.keyring import Keyring
from aws_jumpcloud.profile import Profile
from aws_jumpcloud.saml import get_assertion_roles

_session = None


def get_info(args):
    keyring = Keyring()
    print("")
    email = keyring.get_jumpcloud_email()
    password = keyring.get_jumpcloud_password()
    ts = keyring.get_jumpcloud_timestamp()
    print(f"JumpCloud email: {email or '<not stored>'}")
    print(f"JumpCloud password: {'******** (hidden)' if password else '<not stored>'}")
    print(f"Last JumpCloud authentication: {ts.astimezone().strftime('%c %Z') if ts else '<never>'}")


def list_profiles(args):
    keyring = Keyring()
    profiles = keyring.get_all_profiles()
    sessions = keyring.get_all_sessions()
    if len(profiles) == 0:
        print("")
        print("No profiles found. Use \"aws-jumpcloud add <profile>\" to store a new profile.")
        sys.exit(0)

    print("")
    _print_columns(headers=["Profile", "AWS Account", "AWS Role", "IAM session expires"],
                   rows=_format_profile_rows(profiles, sessions))


def add_profile(args):
    keyring = Keyring()
    if keyring.get_profile(args.profile):
        sys.stderr.write(f"Error: Profile {args.profile} already exists.\n")
        sys.stderr.write("If you want to change the profile defaults, remove the profile\n")
        sys.stderr.write("and add it again.\n")
        sys.exit(1)

    jumpcloud_url = input(f"Enter the JumpCloud SSO URL for {args.profile}: ").strip()
    if not jumpcloud_url.startswith("https://sso.jumpcloud.com/saml2/"):
        sys.stderr.write("Error: That's not a valid JumpCloud SSO URL. SSO URLs must\n")
        sys.stderr.write("start with https://sso.jumpcloud.com/saml2/.\n")
        sys.exit(1)
    profile = Profile(args.profile, jumpcloud_url)
    keyring.store_profile(profile)
    print(f"Profile {args.profile} added.")


def remove_profile(args):
    if args.all:
        _remove_all_profiles(args)
    else:
        _remove_single_profile(args)


def exec_command(args):
    keyring = Keyring()
    profile = keyring.get_profile(args.profile)
    if not profile:
        sys.stderr.write(f"Error: Profile {args.profile} not found; you must add it first.\n")
        sys.exit(1)
    session = keyring.get_session(args.profile)
    if not session:
        _login(keyring, profile)
        session = keyring.get_session(args.profile)

    # Find the full path to the program that the user wants to run, otherwise
    # subprocess.run() won't be able to find it. (I'm not sure exactly why this
    # happens -- it looks like subprocess.run() can find programs in /usr/bin
    # but not /usr/local/bin?)
    result = subprocess.run(["which", args.command[0]], stdout=PIPE)
    if result.returncode == 0 and len(result.stdout.strip()) > 0:
        args.command[0] = result.stdout.strip()
    elif result.returncode == 1:
        sys.stderr.write(f"{args.command[0]}: command not found\n")
        sys.exit(127)
    else:
        sys.stdout.write(result.stdout)
        sys.exit(result.returncode)

    # Run the command that the user wanted, with AWS credentials in the environment
    os.environ['AWS_ACCESS_KEY_ID'] = session.access_key_id
    os.environ['AWS_SECRET_ACCESS_KEY'] = session.secret_access_key
    os.environ['AWS_SECURITY_TOKEN'] = session.session_token
    os.environ['AWS_SESSION_TOKEN'] = session.session_token
    result = subprocess.run(args.command)
    sys.exit(result.returncode)


def rotate_session(args):
    if args.all:
        _rotate_all_sessions(args)
    else:
        _rotate_single_session(args)


def _remove_single_profile(args):
    keyring = Keyring()
    if not keyring.get_profile(args.profile):
        print(f"Profile {args.profile} not found, nothing to do.")
        return
    has_session = not not keyring.get_session(args.profile)
    keyring.delete_session(args.profile)
    keyring.delete_profile(args.profile)
    if has_session:
        print(f"Profile {args.profile} and temporary IAM session removed.")
    else:
        print(f"Profile {args.profile} removed.")


def _remove_all_profiles(args):
    keyring = Keyring()
    keyring.delete_all_data()
    print("")
    print("All configuration profiles, temporary IAM sessions, and JumpCloud login")
    print("credentials have been removed from your OS keychain.")


def _rotate_single_session(args, profile_name=None):
    if not profile_name:
        profile_name = args.profile
    assert(profile_name is not None)

    keyring = Keyring()
    profile = keyring.get_profile(profile_name)
    if not profile:
        sys.stderr.write(f"Error: Profile {profile_name} not found.\n")
        sys.exit(1)

    _get_jumpcloud_session(profile_name)

    keyring.delete_session(profile_name)
    print(f"Temporary IAM session for {profile_name} removed.")

    _login(keyring, profile)
    session = keyring.get_session(profile_name)
    expires_at = session.expires_at.strftime('%c %Z')
    print(f"AWS temporary session rotated; new session valid until {expires_at}.\n")


def _rotate_all_sessions(args):
    keyring = Keyring()
    profiles = keyring.get_all_profiles()
    if len(profiles) == 0:
        print("")
        print("No profiles found. Use \"aws-jumpcloud add <profile>\" to store a new profile.")
        sys.exit(0)

    _get_jumpcloud_session('--all')
    print("")

    for profile in profiles.values():
        _rotate_single_session(args, profile.name)


def _get_jumpcloud_session(profile_name):
    # This function returns a JumpCloudSession with the user logged in. If a
    # session is already exists in the current process, it uses that;
    # otherwise it creates a new one.
    global _session
    if _session:
        return _session

    keyring = Keyring()
    email = keyring.get_jumpcloud_email()
    password = keyring.get_jumpcloud_password()
    if email and password:
        sys.stderr.write("Using JumpCloud login details from your OS keychain.\n")
    elif sys.stdout.isatty():
        email = input("Enter your JumpCloud email address: ").strip()
        password = getpass.getpass("Enter your JumpCloud password: ").strip()
        keyring.store_jumpcloud_email(email)
        keyring.store_jumpcloud_password(password)
        sys.stderr.write("JumpCloud login details saved in your OS keychain.\n")
    else:
        sys.stderr.write(
            "Error: JumpCloud login details not found in your OS keychain.\n"
            f"Run \"{_get_program_name()} rotate {profile_name}\" interactively to\n"
            "store your credentials in the keychain, then try again.\n")
        sys.exit(1)

    session = JumpCloudSession(email, password)
    try:
        session.login()
    except JumpCloudError as e:
        sys.stderr.write(f"\nError: {e.message}\n")
        if isinstance(e, JumpCloudAuthFailure):
            keyring.store_jumpcloud_email(None)
            keyring.store_jumpcloud_password(None)
            sys.stderr.write(
                "- You will be prompted for your username and password "
                "the next time you try.\n")
        elif isinstance(e, JumpCloudMFARequired):
            sys.stderr.write(
                f"Run \"{_get_program_name()} rotate {profile_name}\" interactively to\n"
                "refresh the temporary credentials in your OS keychain, then try again.\n")
        elif isinstance(e, JumpCloudServerError):
            error_msg = e.jumpcloud_error_message or e.response.text
            sys.stderr.write(f"- JumpCloud error message: {error_msg}\n")
        elif isinstance(e, JumpCloudUnexpectedResponse):
            sys.stderr.write(f"- JumpCloud response body: {e.response.text}\n")
        sys.exit(1)

    _session = session
    return _session


def _login(keyring, profile):
    session = _get_jumpcloud_session(profile.name)
    sys.stderr.write("Attempting SSO authentication to Amazon Web Services...\n")
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

    sys.stderr.write("\n")
    return session


def _get_program_name():
    return sys.argv[0]


def _format_profile_rows(profiles, sessions):
    rows = []
    for p in sorted(profiles.values(), key=lambda p: p.name):
        aws_account_desc = p.aws_account_alias or p.aws_account_id or "<unknown>"
        aws_role = p.aws_role or "<unknown>"
        if p.name in sessions:
            expires_at = sessions[p.name].expires_at.astimezone().strftime("%c %Z")
        else:
            expires_at = "<no active session>"
        rows.append([p.name, aws_account_desc, aws_role, expires_at])
    return rows


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
