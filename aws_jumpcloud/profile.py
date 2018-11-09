import json


class Profile(object):
    def __init__(self, name, jumpcloud_url, aws_account_id=None, aws_role=None, aws_account_alias=None):
        self.name = name
        self.jumpcloud_url = jumpcloud_url
        self.aws_account_id = aws_account_id
        self.aws_role = aws_role
        self.aws_account_alias = aws_account_alias

    def dumps(self):
        return json.dumps({"name": self.name,
                           "jumpcloud_url": self.jumpcloud_url,
                           "aws_account_id": self.aws_account_id,
                           "aws_account_alias": self.aws_account_alias,
                           "aws_role": self.aws_role})

    @property
    def role_arn(self):
        assert(self.aws_account_id is not None)
        assert(self.aws_role is not None)
        return f"arn:aws:iam::{self.aws_account_id}:role/{self.aws_role}"

    @classmethod
    def loads(cls, json_string):
        data = json.loads(json_string)
        return Profile(**data)
