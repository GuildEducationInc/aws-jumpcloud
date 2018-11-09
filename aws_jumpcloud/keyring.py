import json

import keyring

from aws_jumpcloud.aws import AWSSession
from aws_jumpcloud.profile import Profile


class Keyring(object):
    def __init__(self, service="aws-jumpcloud", username="credentials"):
        self._keyring_service = service
        self._keyring_username = username
        self._jumpcloud_email = None
        self._jumpcloud_password = None
        self._profiles = None
        self._aws_sessions = None

    # Public method for removing the entire OS keyring object
    def delete_all_data(self):
        if keyring.get_password(self._keyring_service, self._keyring_username) is not None:
            keyring.delete_password(self._keyring_service, self._keyring_username)
        self._load()

    # Public methods for working with JumpCloud login credentials

    @property
    def jumpcloud_email(self):
        self._load()
        return self._jumpcloud_email

    @jumpcloud_email.setter(self, value):
        self._load()
        self._jumpcloud_email = value
        self._save()

    @property
    def jumpcloud_password(self):
        self._load()
        return self._jumpcloud_password

    @jumpcloud_password.setter(self, value):
        self._load()
        self._jumpcloud_password = value
        self._save()

    # Public methods for working with AWS login profiles

    def get_all_profiles(self):
        self._load()
        return self._profiles

    def get_profile(self, name):
        self._load()
        return self._profiles.get(name) or ""

    def store_profile(self, profile):
        self._load()
        self._profiles[profile.name] = profile
        self._save()

    def delete_profile(self, name):
        self._load()
        if name in self._profiles:
            del self._profiles[name]
            self._save()

    # Public methods for working with temporary AWS sessions

    def get_all_sessions(self):
        """Returns all AWS sessions that are present in the OS keyring.
        Expired sessions are automatically removed from the keyring and
        filtered out of the results."""
        self._load()
        return self._aws_sessions

    def get_session(self, profile_name):
        """Returns the AWS session for the given profile name. Returns None if
        not present, or expired. Expired sessions are automatically removed
        from the OS keyring."""
        self._load()
        return self._aws_sessions.get(profile_name) or None

    def store_session(self, profile_name, session):
        """Stores the given AWS session in the OS keyring."""
        if session.expired():
            return
        self._load()
        self._aws_sessions[profile_name] = session
        self._save()

    def delete_session(self, profile_name):
        """Removes the given AWS session from the OS keyring. Does nothing
        if the profile isn't already present."""
        self._load()
        if profile_name not in self._aws_sessions:
            return
        del self._aws_sessions[profile_name]
        self._save()

    # Private methods for working with the OS keychain

    def _load(self):
        """Pulls data from the OS keyring into this object. Automatically
        deletes any expired sessions found in the OS keyring."""
        json_data = keyring.get_password(self._keyring_service, self._keyring_username)
        if json_data is None:
            keyring_data = {}
        else:
            keyring_data = json.loads(json_data)
        self._jumpcloud_email = keyring_data.get("jumpcloud_email") or None
        self._jumpcloud_password = keyring_data.get("jumpcloud_password") or None

        self._profiles = {}
        for profile_str in keyring_data.get("profiles", []):
            profile = Profile.loads(profile_str)
            self._profiles[profile.name] = profile
        self._aws_sessions = {}
        expired_sessions = 0
        for (profile, session_str) in keyring_data.get("aws_sessions", {}).items():
            session = AWSSession.loads(session_str)
            if session.expired():
                # Don't save expired sessions in the dict, and note that we
                # found expired sessions so that we can remove them from the OS
                # keyring
                expired_sessions += 1
            else:
                self._aws_sessions[profile] = session
        if expired_sessions > 0:
            self._save()

    def _save(self):
        """Pushes data from this object into the OS keyring."""
        json_data = json.dumps({
            "jumpcloud_email": self._jumpcloud_email,
            "jumpcloud_password": self._jumpcloud_password,
            "profiles": [p.dumps() for p in self._profiles.values()],
            "aws_sessions": dict([(k, v.dumps()) for (k, v) in self._aws_sessions.items()])
        })
        keyring.set_password(self._keyring_service, self._keyring_username, json_data)
