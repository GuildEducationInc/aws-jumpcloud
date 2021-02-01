import base64
from collections import namedtuple
from datetime import datetime, timedelta, timezone
import json
import re
import time

import boto3

from aws_jumpcloud.saml import get_assertion_duration

# Regular expression to extract an account number and role name from an ARN.
ROLE_ARN_REGEXP = re.compile(r"^arn:aws:iam::([0-9]{12}):role/([\w+=,.@-]+)$")
ParseResult = namedtuple("ArnParts", ["aws_account_id", "aws_role"])

# If the SAML assertion from JumpCloud doesn't include a SessionDuration
# attribute, use a default duration of 60 minutes. Whether using a
# SessionDuration attribute or a default, the duration requested in the
# AssumeRole API call *must* be <= the role's MaxSessionDuration, or the API
# call will fail. (Don't set your JumpCloud SessionDuration higher than your
# AWS MaxSessionDuration!)
DEFAULT_DURATION = 60 * 60  # in seconds


class AWSSession(object):
    def __init__(self, access_key_id, secret_access_key, session_token, expires_at):
        assert isinstance(access_key_id, str)
        assert isinstance(secret_access_key, str)
        assert isinstance(session_token, str)
        assert isinstance(expires_at, datetime)
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.expires_at = expires_at

    def expired(self):
        return self.expires_at < datetime.now(timezone.utc)

    def dumps(self):
        return json.dumps(
            {
                "access_key_id": self.access_key_id,
                "secret_access_key": self.secret_access_key,
                "session_token": self.session_token,
                "expires_at": self.expires_at.timestamp(),
            }
        )

    def get_environment_vars(self):
        return {
            "AWS_ACCESS_KEY_ID": self.access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.secret_access_key,
            "AWS_SECURITY_TOKEN": self.session_token,
            "AWS_SESSION_TOKEN": self.session_token,
        }

    @classmethod
    def loads(cls, json_string):
        data = json.loads(json_string)
        data["expires_at"] = datetime.fromtimestamp(data["expires_at"], tz=timezone.utc)
        return AWSSession(**data)

    @classmethod
    def from_sts(cls, sts_resp):
        assert sts_resp["ResponseMetadata"]["HTTPStatusCode"] == 200
        return AWSSession(
            access_key_id=sts_resp["Credentials"]["AccessKeyId"],
            secret_access_key=sts_resp["Credentials"]["SecretAccessKey"],
            session_token=sts_resp["Credentials"]["SessionToken"],
            expires_at=sts_resp["Credentials"]["Expiration"],
        )


def assume_role_with_saml(saml_role, saml_assertion_xml):
    client = boto3.client("sts")
    duration = get_assertion_duration(saml_assertion_xml) or DEFAULT_DURATION
    sts_resp = client.assume_role_with_saml(
        RoleArn=saml_role.role_arn,
        PrincipalArn=saml_role.principal_arn,
        SAMLAssertion=base64.b64encode(saml_assertion_xml).decode("ascii"),
        DurationSeconds=duration,
    )
    return AWSSession.from_sts(sts_resp)


def get_account_alias(session):
    try:
        client = boto3.client(
            "iam",
            aws_access_key_id=session.access_key_id,
            aws_secret_access_key=session.secret_access_key,
            aws_session_token=session.session_token,
        )
        resp = client.list_account_aliases()
        assert resp["ResponseMetadata"]["HTTPStatusCode"] == 200
        return resp["AccountAliases"][0] if resp["AccountAliases"] else None
    except Exception:
        # This is optional functionality, so ignore exceptions
        return None


def is_arn(role_arn):
    return not not ROLE_ARN_REGEXP.match(role_arn)


def parse_arn(role_arn):
    return ParseResult(*ROLE_ARN_REGEXP.match(role_arn).groups())


def build_arn(aws_account_id, role_name):
    return f"arn:aws:iam::{aws_account_id}:role/{role_name}"


def assume_role(session, role_to_assume, role_session_name):
    client = boto3.client(
        "sts",
        aws_access_key_id=session.access_key_id,
        aws_secret_access_key=session.secret_access_key,
        aws_session_token=session.session_token,
    )
    if role_to_assume.external_id:
        kwargs = {"ExternalId": role_to_assume.external_id}
    else:
        kwargs = {}
    sts_resp = client.assume_role(
        RoleArn=role_to_assume.arn, RoleSessionName=role_session_name, **kwargs
    )
    return AWSSession.from_sts(sts_resp)


def get_role_session_name(user_identifier):
    return "-".join(["aws-jumpcloud", user_identifier, str(int(time.time()))])
