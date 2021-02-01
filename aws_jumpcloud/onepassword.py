from shutil import which
import sys
import os
import subprocess
import json

ITEM = "jumpcloud"


def installed():
    hasop = which("op") is not None and which("op") is not True
    if hasop:
        if os.getenv("OP_SUBDOMAIN") and subprocess.call(
            "op get account", shell=True
        ):  # returns truthy non-zero exit code if no active op CLI session
            subprocess.check_call("eval $(op signin $OP_SUBDOMAIN)", shell=True)
        if not os.getenv("OP_SUBDOMAIN"):
            raise OnePasswordNotSignedIn()
    return hasop


def get_email():
    email = _get_field("email")
    if not email:
        email = _get_field("username")
    # if no email at this point, raise?
    return email


def get_password():
    return _get_field("password")


def _get_field(field):
    item = _get_item()

    if not item:
        return None

    fields = item["details"]["fields"]
    return next(
        (item.get("value") for item in fields if item.get("name") == field), None
    )


def _get_item():
    raw = _cmd(f"get item {ITEM}")

    if raw:
        return json.loads(raw)
    else:
        return None


def get_totp():
    return _cmd(f"get totp {ITEM}")


def _cmd(cmd):
    return (
        subprocess.check_output(f"op {cmd}", shell=True)
        .decode(sys.stdout.encoding)
        .strip()
    )


class OnePasswordNotSignedIn(Exception):
    def __init__(self):
        message = """
            1Password CLI is not signed in. Either export your 1Password subdomain (e.g. duff-beer):
                export OP_SUBDOMAIN=duff-beer
            or manually sign in with:
                eval $(op signin duff-beer)
            and try again.
        """
        Exception.__init(self, message)
        self.message = message
