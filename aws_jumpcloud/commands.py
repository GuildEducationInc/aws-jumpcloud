from argparse import ArgumentParser
import getpass
import os
import sys
import subprocess
import textwrap
from subprocess import PIPE

from aws_jumpcloud.aws import assume_role, assume_role_with_saml
from aws_jumpcloud.aws import get_account_alias, get_role_session_name
from aws_jumpcloud.aws import is_arn, parse_arn
from aws_jumpcloud.jumpcloud import (
    JumpCloudSession,
    JumpCloudError,
    JumpCloudAuthFailure,
)
from aws_jumpcloud.jumpcloud import JumpCloudMFARequired, JumpCloudServerError
from aws_jumpcloud.jumpcloud import (
    JumpCloudUnexpectedStatus,
    JumpCloudMissingSAMLResponse,
)
from aws_jumpcloud.keyring import Keyring
from aws_jumpcloud.profile import AssumedRole, Profile
from aws_jumpcloud.saml import get_assertion_roles
import aws_jumpcloud.onepassword as op

_session = None


def get_info(args):
    keyring = Keyring()
    print("")
    email = keyring.get_jumpcloud_email()
    password = keyring.get_jumpcloud_password()
    ts = keyring.get_jumpcloud_timestamp()
    print(f"JumpCloud email: {email or '<not stored>'}")
    print(f"JumpCloud password: {'******** (hidden)' if password else '<not stored>'}")
    print(
        f"Last JumpCloud authentication: {ts.astimezone().strftime('%c %Z') if ts else '<never>'}"
    )


def list_profiles(args):
    keyring = Keyring()
    profiles = keyring.get_all_profiles()
    sessions = keyring.get_all_sessions()
    if len(profiles) == 0:
        print("")
        print(
            'No profiles found. Use "aws-jumpcloud add <profile>" to store a new profile.'
        )
        sys.exit(0)

    print("")
    _print_columns(
        headers=["Profile", "AWS Account", "AWS Role", "IAM session expires"],
        rows=_format_profile_rows(profiles, sessions),
    )


def add_profile(args):
    if args.external_id and not args.role_to_assume:
        _print_error("Error: Cannot use --external-id without --role.")
        sys.exit(1)

    keyring = Keyring()
    if keyring.get_profile(args.profile):
        _print_error(
            f'Error: Profile "{args.profile}" already exists. If you want to modify '
            "the profile, remove the profile and add it again."
        )
        sys.exit(1)

    jumpcloud_url = args.url or input(
        f'Enter the JumpCloud SSO URL for "{args.profile}": '
    )
    jumpcloud_url = jumpcloud_url.strip()
    if not jumpcloud_url.startswith("https://sso.jumpcloud.com/saml2/"):
        _print_error(
            "Error: That's not a valid JumpCloud SSO URL. SSO URLs must "
            'start with "https://sso.jumpcloud.com/saml2/".'
        )
        sys.exit(1)
    if args.role_to_assume:
        if is_arn(args.role_to_assume):
            arn_parts = parse_arn(args.role_to_assume)
            assumed_role = AssumedRole(
                aws_account_id=arn_parts.aws_account_id,
                aws_role=arn_parts.aws_role,
                external_id=args.external_id,
            )
        else:
            assumed_role = AssumedRole(
                aws_account_id=None,
                aws_role=args.role_to_assume,
                external_id=args.external_id,
            )
    else:
        assumed_role = None
    profile = Profile(args.profile, jumpcloud_url, assumed_role)
    keyring.store_profile(profile)
    print(f'Profile "{args.profile}" added.')


def is_active(args):
    keyring = Keyring()
    sess = keyring.get_session(args.profile)

    if sess and not sess.expired():
        print(1)


def remove_profile(args):
    if args.all:
        _remove_all_profiles(args)
    else:
        _remove_single_profile(args)


def exec_command(args):
    # Run the command that the user wanted, with AWS credentials in the environment
    session = _get_aws_session(args.profile)
    args.command[0] = _which(args.command[0])
    for (name, value) in session.get_environment_vars().items():
        os.environ[name] = value
    result = subprocess.run(args.command)
    sys.exit(result.returncode)


def export_vars(args):
    # Print export statements for a profile's AWS credentials
    session = _get_aws_session(args.profile)
    for (name, value) in session.get_environment_vars().items():
        print(f'export {name}="{value}"')


def rotate_session(args):
    if args.all:
        _rotate_all_sessions(args)
    else:
        _rotate_single_session(args)


def _remove_single_profile(args):
    keyring = Keyring()
    if not keyring.get_profile(args.profile):
        print(f'Profile "{args.profile}" not found, nothing to do.')
        return
    has_session = not not keyring.get_session(args.profile)
    keyring.delete_session(args.profile)
    keyring.delete_profile(args.profile)
    if has_session:
        print(f'Profile "{args.profile}" and temporary IAM session removed.')
    else:
        print(f'Profile "{args.profile}" removed.')


def _remove_all_profiles(args):
    keyring = Keyring()
    keyring.delete_all_data()
    print("")
    print("All configuration profiles, temporary IAM sessions, and JumpCloud login")
    print("credentials have been removed from your OS keychain.")


def _rotate_single_session(args, profile_name=None):
    if not profile_name:
        profile_name = args.profile
    assert profile_name is not None

    keyring = Keyring()
    profile = keyring.get_profile(profile_name)
    if not profile:
        sys.stderr.write(f'Error: Profile "{profile_name}" not found.\n')
        sys.exit(1)

    _login_to_jumpcloud(profile_name)

    keyring.delete_session(profile_name)
    print(f'Temporary IAM session for "{profile_name}" removed.')

    _login_to_aws(keyring, profile)
    session = keyring.get_session(profile_name)
    expires_at = session.expires_at.strftime("%c %Z")
    print(f"AWS temporary session rotated; new session valid until {expires_at}.\n")


def _rotate_all_sessions(args):
    keyring = Keyring()
    profiles = keyring.get_all_profiles()
    if len(profiles) == 0:
        print("")
        print(
            'No profiles found. Use "aws-jumpcloud add <profile>" to store a new profile.'
        )
        sys.exit(0)

    _login_to_jumpcloud("--all")
    print("")

    for profile in profiles.values():
        _rotate_single_session(args, profile.name)


def _get_aws_session(profile_name):
    # Validates the profile parameter and returns the profile's AWS session,
    # going through the single sign-on process if necessary. This is a wrapper
    # around _login_to_jumpcloud() and _login_to_aws().
    keyring = Keyring()
    profile = keyring.get_profile(profile_name)
    if not profile:
        _print_error(
            f'Error: Profile "{profile_name}" not found; you must add it first.'
        )
        sys.exit(1)
    session = keyring.get_session(profile_name)
    if not session:
        _login_to_aws(keyring, profile)
        session = keyring.get_session(profile_name)
    return session


def _input_email():
    return input("Enter your JumpCloud email address: ").strip()


def _input_password():
    return getpass.getpass("Enter your JumpCloud password: ").strip()


def _get_email():
    if op.installed():
        sys.stderr.write(f"1Password CLI found. Using email from item: {op.ITEM}\n")
        email = op.get_email()

        if email:
            return email
        else:
            sys.stderr.write(
                f"1Password email not found for item: {op.ITEM}. "
                "Falling back to user input.\n"
            )
            return _input_email()
    else:
        return _input_email()


def _get_password():
    if op.installed():
        sys.stderr.write(f"1Password CLI found. Using password from item: {op.ITEM}\n")
        passwd = op.get_password()

        if passwd:
            return passwd
        else:
            sys.stderr.write(
                f"1Password password not found for item: {op.ITEM}. "
                "Falling back to user input.\n"
            )
            return _input_password()
    else:
        return _input_password()


def _login_to_jumpcloud(profile_name):
    # Returns a JumpCloudSession with the user logged in. If a session already
    # in the current process, it uses that; otherwise it creates a new one.
    global _session
    if _session:
        return _session

    keyring = Keyring()
    email = keyring.get_jumpcloud_email()
    password = keyring.get_jumpcloud_password()
    if email and password:
        sys.stderr.write("Using JumpCloud login details from your OS keychain.\n")
    elif sys.stdout.isatty():
        email = _get_email()
        password = _get_password()
        keyring.store_jumpcloud_email(email)
        keyring.store_jumpcloud_password(password)
        sys.stderr.write("JumpCloud login details saved in your OS keychain.\n")
    else:
        _print_error(
            "Error: JumpCloud login details not found in your OS keychain. "
            f'Run "{_get_program_name()} rotate {profile_name}" interactively '
            "to store your credentials in the keychain, then try again."
        )
        sys.exit(1)

    session = JumpCloudSession(email, password)
    try:
        session.login()
    except JumpCloudError as e:
        sys.stderr.write("\n")
        _print_error(f"Error: {e.message}")
        if isinstance(e, JumpCloudAuthFailure):
            keyring.store_jumpcloud_email(None)
            keyring.store_jumpcloud_password(None)
            _print_error(
                "- You will be prompted for your username and password the next time you try."
            )
        elif isinstance(e, JumpCloudMFARequired):
            _print_error(
                f'Run "{_get_program_name()} rotate {profile_name}" interactively to '
                "refresh the temporary credentials in your OS keychain, then try again."
            )
        elif isinstance(e, JumpCloudServerError):
            _print_error(
                f"- JumpCloud error message: {e.jumpcloud_error_message or e.response.text}"
            )
        sys.exit(1)

    _session = session
    return _session


def _login_to_aws(keyring, profile):
    # Returns an AWSSession with temporary credentials for the given profile.
    session = _login_to_jumpcloud(profile.name)
    sys.stderr.write("Attempting SSO authentication to Amazon Web Services...\n")
    try:
        saml_assertion = session.get_aws_saml_assertion(profile)
    except JumpCloudError as e:
        sys.stderr.write("\n")
        _print_error(f"Error: {e.message}")
        if isinstance(e, JumpCloudServerError):
            _print_error(
                f"- JumpCloud error message: {e.jumpcloud_error_message or e.response.text}"
            )
        elif isinstance(e, JumpCloudMissingSAMLResponse):
            sys.stderr.write("\n")
            _print_error(
                "You may have been removed from the Single-Sign On Application for the profile "
                f'"{profile.name}", or its URL may be be incorrect. You can check the URL by '
                "visiting the JumpCloud Console in your web browser and confirming that one of "
                f'the Single Sign-On Applications has the URL "{profile.jumpcloud_url}". If '
                "the URL is correct, aws-jumpcloud may need to be updated."
            )
        sys.exit(1)
    roles = get_assertion_roles(saml_assertion)

    # Warning: It's a valid JumpCloud configuration to present more than one
    # role in the assertion, but we don't use that feature right now. We
    # should handle that situation properly at some point.
    assert len(roles) == 1
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

    # Update the AWS account alias on each login. The alias refers to the
    # account used to login, not any assumed role (which happens below).
    alias = get_account_alias(session)
    if alias != profile.aws_account_alias:
        profile.aws_account_alias = alias
        keyring.store_profile(profile)

    if profile.role_to_assume:
        if not profile.role_to_assume.aws_account_id:
            profile.role_to_assume.aws_account_id = profile.aws_account_id
            keyring.store_profile(profile)
        sys.stderr.write(f"Assuming role {profile.role_to_assume.arn}...\n")
        email = keyring.get_jumpcloud_email()
        role_session_name = get_role_session_name(email)
        session = assume_role(session, profile.role_to_assume, role_session_name)

    keyring.store_session(profile.name, session)
    sys.stderr.write("\n")
    return session


def _which(command):
    # Find the full path to the program that the user wants to run, otherwise
    # subprocess.run() won't be able to find it. (I'm not sure exactly why this
    # happens -- it looks like subprocess.run() can find programs in /usr/bin
    # but not /usr/local/bin?)
    result = subprocess.run(["which", command], stdout=PIPE)
    if result.returncode == 1:
        sys.stderr.write(f"{command}: command not found\n")
        sys.exit(127)
    elif result.returncode > 0 or len(result.stdout.strip()) == 0:
        sys.stdout.write(result.stdout)
        sys.exit(result.returncode)
    return result.stdout.strip()


def _get_program_name():
    return sys.argv[0]


def _format_profile_rows(profiles, sessions):
    rows = []
    for p in sorted(profiles.values(), key=lambda p: p.name):
        if p.role_to_assume and p.role_to_assume.aws_account_id:
            aws_account_desc = p.role_to_assume.aws_account_id
        else:
            aws_account_desc = p.aws_account_alias or p.aws_account_id or "<unknown>"
        if p.role_to_assume:
            aws_role = p.role_to_assume.aws_role
        else:
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


def _print_error(message):
    formatted_message = "\n".join(textwrap.wrap(message)) + "\n"
    sys.stderr.write(formatted_message)
