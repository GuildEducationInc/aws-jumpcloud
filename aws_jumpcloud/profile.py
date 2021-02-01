import json

from aws_jumpcloud.aws import build_arn, parse_arn


class Profile(object):
    def __init__(self, name, jumpcloud_url, role_to_assume=None):
        self.name = name
        self.jumpcloud_url = jumpcloud_url
        self.aws_account_id = None
        self.aws_role = None
        self.aws_account_alias = None
        self.role_to_assume = role_to_assume

    @property
    def role_arn(self):
        assert self.aws_account_id is not None
        assert self.aws_role is not None
        return build_arn(self.aws_account_id, self.aws_role)

    def dumps(self):
        return json.dumps(
            {
                "name": self.name,
                "jumpcloud_url": self.jumpcloud_url,
                "aws_account_id": self.aws_account_id,
                "aws_account_alias": self.aws_account_alias,
                "aws_role": self.aws_role,
                "role_to_assume": self.role_to_assume.dumps()
                if self.role_to_assume
                else None,
            }
        )

    @classmethod
    def loads(cls, json_string):
        data = json.loads(json_string)
        p = Profile(name=data["name"], jumpcloud_url=data["jumpcloud_url"])
        p.aws_account_id = data["aws_account_id"]
        p.aws_role = data["aws_role"]
        p.aws_account_alias = data["aws_account_alias"]
        if data.get("role_to_assume") is not None:
            p.role_to_assume = AssumedRole.loads(data["role_to_assume"])
        return p


class AssumedRole(object):
    def __init__(self, aws_account_id, aws_role, external_id):
        self.aws_account_id = aws_account_id
        self.aws_role = aws_role
        self.external_id = external_id

    @property
    def arn(self):
        if self.aws_account_id:
            return build_arn(self.aws_account_id, self.aws_role)
        else:
            return None

    def dumps(self):
        return json.dumps(
            {
                "aws_account_id": self.aws_account_id,
                "aws_role": self.aws_role,
                "external_id": self.external_id,
            }
        )

    @classmethod
    def loads(cls, json_string):
        data = json.loads(json_string)
        return AssumedRole(**data)
