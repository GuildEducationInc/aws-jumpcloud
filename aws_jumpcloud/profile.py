import json


class Profile(object):
    def __init__(self, name, jumpcloud_url):
        self.name = name
        self.jumpcloud_url = jumpcloud_url
        self.aws_account_id = None
        self.aws_role = None
        self.aws_account_alias = None

    @property
    def role_arn(self):
        assert(self.aws_account_id is not None)
        assert(self.aws_role is not None)
        return f"arn:aws:iam::{self.aws_account_id}:role/{self.aws_role}"

    def dumps(self):
        return json.dumps({"name": self.name,
                           "jumpcloud_url": self.jumpcloud_url,
                           "aws_account_id": self.aws_account_id,
                           "aws_account_alias": self.aws_account_alias,
                           "aws_role": self.aws_role})

    @classmethod
    def loads(cls, json_string):
        data = json.loads(json_string)
        p = Profile(name=data['name'], jumpcloud_url=data['jumpcloud_url'])
        p.aws_account_id = data['aws_account_id']
        p.aws_role = data['aws_role']
        p.aws_account_alias = data['aws_account_alias']
        return p
