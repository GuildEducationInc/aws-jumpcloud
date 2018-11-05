from argparse import ArgumentParser
import getpass
import os

import keyring

from aws_jumpcloud.jumpcloud import JumpCloudSession
from aws_jumpcloud.aws import AWSCredentials, assume_role_with_saml
from aws_jumpcloud.saml import get_assertion_roles

JUMPCLOUD_KEYCHAIN_NAME = "aws-jumpcloud"
AWS_KEYCHAIN_NAME = "aws-jumpcloud temporary credentials"


def get_password(email):
    password = keyring.get_password(JUMPCLOUD_KEYCHAIN_NAME, email)
    if password:
        print("Found your JumpCloud password in your macOS keychain.")
    else:
        password = getpass.getpass("Enter your JumpCloud password: ").strip()
        if len(password) == 0:
            return None
        resp = input("Would you like to store this in your macOS keychain [yes/no]? ")
        if resp.lower() == 'yes':
            keyring.set_password(JUMPCLOUD_KEYCHAIN_NAME, email, password)
    print("")
    return password


def main():
    # aws-jumpcloud help
    # aws-jumpcloud list : list profiles, along with their credentials and sessions
    # aws-jumpcloud add <profile> : adds the specified profile to your keyring
    # aws-jumpcloud rotate <profile> : rotates credentials
    # aws-jumpcloud exec <profile> <cmd> : executes a command with AWS credentials in the environment
    # aws-jumpcloud remove <profile> : removes credentials, including sessions

    parser = ArgumentParser()
    parser.add_argument("--debug", help="Show debugging output", action="store_true")

    args = parser.parse_args()

    email = os.environ.get("JUMPCLOUD_EMAIL") or input("Enter your JumpCloud email address: ")
    password = get_password(email)

    j = JumpCloudSession(email, password)
    j.login()

    saml_assertion_xml = j.get_aws_saml_assertion()
    roles = get_assertion_roles(saml_assertion_xml)
    if len(roles) > 1:
        print("Please select a role to assume:")
        for i, role in enumerate(roles):
            print(f"   {i + 1}. {role.role_arn}")
        choice = input("Role: ")
        role = roles[int(choice) - 1]
    else:
        role = roles[0]

    creds = assume_role_with_saml(role, saml_assertion_xml)
    print("")
    print(f"# Credentials for {role.role_arn} (expires at {creds.expires_at.strftime('%c %Z')})")
    print(f"export AWS_ACCESS_KEY_ID={creds.access_key_id}")
    print(f"export AWS_SECRET_ACCESS_KEY={creds.secret_access_key}")
    print(f"export AWS_SESSION_TOKEN={creds.session_token}")
    print("")
    print(creds.dumps())


if __name__ == "__main__":
    main()
