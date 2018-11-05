import json

import keyring

from aws_jumpcloud.aws import AWSCredentials


class Keychain(object):
    def __init__(self, email, service="aws-jumpcloud"):
        self._keyring_service = service
        self._keyring_username = email
        self._jumpcloud_email = None
        self._jumpcloud_password = None
        self._aws_credentials = None

    def get_jumpcloud_login(self):
        """Retrieves the saved JumpCloud login from the OS keychain. Returns an
        (email, password) tuple, or (None, None) if not found."""
        self._load()
        return (self._jumpcloud_email, self._jumpcloud_password)

    def store_email_and_password(self, email, password):
        """Stores the JumpCloud login credentials in the OS keychain."""
        self._load()
        self._jumpcloud_email = email
        self._jumpcloud_password = password
        self._save()

    def list_aws_credentials(self):
        """Returns all AWS credentials that are present in the OS keychain.
        Expired credentials are automatically removed from the keychain and
        filtered out of the results."""
        self._load()
        return self._aws_credentials

    def get_credentials(self, profile):
        """Returns AWS credentials for the given profile name. Returns None if
        not present, or expired. Expired credentials are automatically removed
        from the keychain."""
        self._load()
        return self._aws_credentials.get(profile) or None

    def store_credentials(self, profile, creds):
        """Stores the given AWS credentials in the OS keychain."""
        if creds.expired():
            return
        self._load()
        self._aws_credentials[profile] = creds
        self._save()

    def delete_credentials(self, profile):
        """Removes the given AWS credentials from the OS keychain. Does nothing
        if the profile isn't already present."""
        self._load()
        if profile not in self._aws_credentials:
            return
        del self._aws_credentials[profile]
        self._save()

    def _load(self):
        json_data = keyring.get_password(self._keyring_service, self._keyring_username)
        if json_data is None:
            keyring_data = {}
        else:
            keyring_data = json.loads(json_data)
        self._jumpcloud_email = keyring_data.get("jumpcloud_email") or None
        assert(self._jumpcloud_email is None or self._jumpcloud_email == self._keyring_username)
        self._jumpcloud_password = keyring_data.get("jumpcloud_password") or None
        self._aws_credentials = {}
        for (profile, creds_str) in keyring_data.get("aws_credentials", {}).items():
            self._aws_credentials[profile] = AWSCredentials.loads(creds_str)
        self.loaded = True
        self._remove_expired_creds()

    def _save(self):
        data = {"jumpcloud_email": self._jumpcloud_email,
                "jumpcloud_password": self._jumpcloud_password,
                "aws_credentials": dict([(k, v.dumps()) for (k, v) in self._aws_credentials.items()])}
        json_data = json.dumps({
            "jumpcloud_email": self._jumpcloud_email,
            "jumpcloud_password": self._jumpcloud_password,
            "aws_credentials": dict([(k, v.dumps()) for (k, v) in self._aws_credentials.items()])
        })
        keyring.set_password(self._keyring_service, self._keyring_username, json_data)

    def _remove_expired_creds(self):
        if not self.loaded:
            self._load()
        dirty = False
        for profile in list(self._aws_credentials.keys()):
            if self._aws_credentials[profile].expired():
                del self._aws_credentials[profile]
                dirty = True
        if dirty:
            self._save()
