import base64
from datetime import datetime, timedelta, timezone
import json

import boto3

# The default duration for an STS session is 15 minutes. This must be within
# the role's MaxSessionDuration, but we can't validate that in advance of
# attempting to call AssumeRole, so we'll leave it at 15 minutes. The actual
# duration for a session will be lesser of this or the SAML assertion's
# SessionDuration.
SESSION_DURATION = timedelta(minutes=15)


class AWSCredentials(object):
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
        return AWSCredentials(**data)


def assume_role_with_saml(saml_role, saml_assertion_xml):
    client = boto3.client('sts')
    sts_resp = client.assume_role_with_saml(
        RoleArn=saml_role.role_arn,
        PrincipalArn=saml_role.principal_arn,
        SAMLAssertion=base64.b64encode(saml_assertion_xml).decode("ascii"),
        DurationSeconds=int(SESSION_DURATION.total_seconds())
    )
    assert(sts_resp['ResponseMetadata']['HTTPStatusCode'] == 200)

    return AWSCredentials(access_key_id=sts_resp['Credentials']['AccessKeyId'],
                          secret_access_key=sts_resp['Credentials']['SecretAccessKey'],
                          session_token=sts_resp['Credentials']['SessionToken'],
                          expires_at=sts_resp['Credentials']['Expiration'])
