from shutil import which
import os
import json

ITEM = "jumpcloud"


def installed():
    return which("op") is not None


def get_email():
    return _get_field("email")


def get_password():
    return _get_field("password")


def _get_field(field):
    item = _get_item()

    if not item:
        return None

    fields = item['details']['fields']
    return next(item.get('value') for item in fields if item.get('name') == field)


def _get_item():
    raw = _cmd(f"get item {ITEM}")

    if raw:
        return json.loads(raw)
    else:
        return None


def get_totp():
    return _cmd("get totp")


def _cmd(cmd):
    return os.popen(f'op {cmd} {ITEM}').read().strip()
