import base64
from collections import namedtuple
from datetime import datetime, timedelta, timezone
import json
import re

import boto3

# Regular expression to extract an account number and role name from an ARN.
ROLE_ARN_REGEXP = re.compile(r"^arn:aws:iam::([0-9]{12}):role/([\w+=,.@-]+)$")
ParseResult = namedtuple("ArnParts", ["aws_account_id", "aws_role"])

# Our default duration for an STS session is 60 minutes. This must be within
# the role's MaxSessionDuration, but we can't validate that in advance of
# attempting to call AssumeRole, so we'll try for 60 minutes. The actual
# duration for a session will be lesser of this or the SAML assertion's
# SessionDuration.
SESSION_DURATION = timedelta(minutes=60)


class AWSSession(object):
    def __init__(self, access_key_id, secret_access_key, session_token, expires_at):
        assert(isinstance(access_key_id, str))
        assert(isinstance(secret_access_key, str))
        assert(isinstance(session_token, str))
        assert(isinstance(expires_at, datetime))
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.expires_at = expires_at

    def expired(self):
        return self.expires_at < datetime.now(timezone.utc)

    def dumps(self):
        return json.dumps({"access_key_id": self.access_key_id,
                           "secret_access_key": self.secret_access_key,
                           "session_token": self.session_token,
                           "expires_at": self.expires_at.timestamp()})

    @classmethod
    def loads(cls, json_string):
        data = json.loads(json_string)
        data['expires_at'] = datetime.fromtimestamp(data['expires_at'], tz=timezone.utc)
        return AWSSession(**data)


def assume_role_with_saml(saml_role, saml_assertion_xml):
    client = boto3.client('sts')
    sts_resp = client.assume_role_with_saml(
        RoleArn=saml_role.role_arn,
        PrincipalArn=saml_role.principal_arn,
        SAMLAssertion=base64.b64encode(saml_assertion_xml).decode("ascii"),
        DurationSeconds=int(SESSION_DURATION.total_seconds())
    )
    assert(sts_resp['ResponseMetadata']['HTTPStatusCode'] == 200)

    return AWSSession(access_key_id=sts_resp['Credentials']['AccessKeyId'],
                      secret_access_key=sts_resp['Credentials']['SecretAccessKey'],
                      session_token=sts_resp['Credentials']['SessionToken'],
                      expires_at=sts_resp['Credentials']['Expiration'])


def get_account_alias(session):
    client = boto3.client("iam", aws_access_key_id=session.access_key_id,
                          aws_secret_access_key=session.secret_access_key,
                          aws_session_token=session.session_token)
    resp = client.list_account_aliases()
    assert(resp['ResponseMetadata']['HTTPStatusCode'] == 200)
    return resp['AccountAliases'][0] if resp['AccountAliases'] else None
    try:
        client = boto3.client("iam", access_key_id=session.access_key_id,
                              secret_access_key=session.secret_access_key,
                              session_token=session.session_token)
        resp = client.list_account_aliases()
        assert(resp['ResponseMetadata']['HTTPStatusCode'] == 200)
        return resp['AccountAliases'][0] if resp['AccountAliases'] else None
    except Exception:
        # This is optional functionality, so ignore exceptions
        return None


def parse_arn(role_arn):
    return ParseResult(*ROLE_ARN_REGEXP.match(role_arn).groups())
