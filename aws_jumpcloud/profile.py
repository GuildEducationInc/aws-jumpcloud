import json


class Profile(object):
    def __init__(self, name, aws_account_id, aws_role, default_region):
        self.name = name
        self.aws_account_id = aws_account_id
        self.aws_role = aws_role
        self.default_region = default_region

    def dumps(self):
        return json.dumps({"name": self.name,
                           "aws_account_id": self.aws_account_id,
                           "aws_role": self.aws_role,
                           "default_region": self.default_region})

    @property
    def role_arn(self):
        return f"arn:aws:iam::{self.aws_account_id}:role/{self.aws_role}"

    @classmethod
    def loads(cls, json_string):
        data = json.loads(json_string)
        return Profile(**data)
