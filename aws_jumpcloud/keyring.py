from datetime import datetime, timezone
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
        self._jumpcloud_timestamp = None
        self._profiles = None
        self._aws_sessions = None

    # Public method for removing the entire OS keyring object
    def delete_all_data(self):
        if (
            keyring.get_password(self._keyring_service, self._keyring_username)
            is not None
        ):
            keyring.delete_password(self._keyring_service, self._keyring_username)
        self._load()

    # Public methods for working with JumpCloud login credentials

    def get_jumpcloud_email(self):
        self._load()
        return self._jumpcloud_email

    def store_jumpcloud_email(self, value):
        self._load()
        self._jumpcloud_email = value
        self._save()

    def get_jumpcloud_password(self):
        self._load()
        return self._jumpcloud_password

    def store_jumpcloud_password(self, value):
        self._load()
        self._jumpcloud_password = value
        self._save()

    def get_jumpcloud_timestamp(self):
        self._load()
        return self._jumpcloud_timestamp

    def store_jumpcloud_timestamp(self, value):
        self._load()
        self._jumpcloud_timestamp = value
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
        keyring_data = self._load_raw_keyring_data()
        self._jumpcloud_email = keyring_data.get("jumpcloud_email") or None
        self._jumpcloud_password = keyring_data.get("jumpcloud_password") or None
        timestamp = keyring_data.get("jumpcloud_timestamp")
        if timestamp:
            self._jumpcloud_timestamp = datetime.fromtimestamp(
                timestamp, tz=timezone.utc
            )
        else:
            self._jumpcloud_timestamp = None

        self._profiles = {}
        for profile_str in keyring_data.get("profiles", []):
            p = Profile.loads(profile_str)
            self._profiles[p.name] = p

        self._aws_sessions = {}
        for (profile, session_str) in keyring_data.get("aws_sessions", {}).items():
            session = AWSSession.loads(session_str)
            self._aws_sessions[profile] = session

        self._purge_expired_sessions()

    def _load_raw_keyring_data(self):
        json_data = keyring.get_password(self._keyring_service, self._keyring_username)
        if json_data is None:
            return {}
        else:
            return json.loads(json_data)

    def _purge_expired_sessions(self):
        expired_sessions = [
            name for (name, session) in self._aws_sessions.items() if session.expired()
        ]
        for p in expired_sessions:
            del self._aws_sessions[p]
        if expired_sessions:
            self._save()

    def _save(self):
        """Pushes data from this object into the OS keyring."""
        if self._jumpcloud_timestamp:
            timestamp = self._jumpcloud_timestamp.timestamp()
        else:
            timestamp = None
        json_data = json.dumps(
            {
                "jumpcloud_email": self._jumpcloud_email,
                "jumpcloud_password": self._jumpcloud_password,
                "jumpcloud_timestamp": timestamp,
                "profiles": [p.dumps() for p in self._profiles.values()],
                "aws_sessions": dict(
                    [(k, v.dumps()) for (k, v) in self._aws_sessions.items()]
                ),
            }
        )
        keyring.set_password(self._keyring_service, self._keyring_username, json_data)
