import base64
from datetime import datetime, timezone
from json import JSONDecodeError
import sys

from bs4 import BeautifulSoup  # pylint: disable=E0401
from requests import Session as HTTPSession

from aws_jumpcloud.keyring import Keyring


class JumpCloudSession(object):
    HTTP_TIMEOUT = 5

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.http = HTTPSession()
        self.logged_in = False
        self.xsrf_token = None

    def login(self):
        try:
            self._authenticate()
        except JumpCloudMFARequired as e:
            if sys.stdout.isatty():
                otp = input("Enter your JumpCloud multi-factor auth code: ").strip()
                self._authenticate(otp=otp)
            else:
                raise e

    def _authenticate(self, otp=None):
        assert(not self.logged_in)
        headers = {'Content-Type': 'application/json',
                   'X-Requested-With': 'XMLHttpRequest',
                   'X-Xsrftoken': self._get_xsrf_token()}
        data = {"email": self.email, "password": self.password}
        if otp is not None:
            data['otp'] = otp
        auth_resp = self.http.post("https://console.jumpcloud.com/userconsole/auth",
                                   headers=headers, json=data, allow_redirects=False,
                                   timeout=JumpCloudSession.HTTP_TIMEOUT)
        if auth_resp.status_code == 200:
            self.logged_in = True
            Keyring().store_jumpcloud_timestamp(datetime.now(tz=timezone.utc))
        elif otp is None and auth_resp.status_code == 302 and "error=4014" in auth_resp.headers['Location']:
            raise JumpCloudMFARequired(auth_resp)
        elif auth_resp.status_code == 401:
            try:
                if otp is not None and "multifactor" in auth_resp.json().get("error"):
                    raise JumpCloudMFAFailure(auth_resp)
            except JSONDecodeError:
                pass
            raise JumpCloudAuthFailure(auth_resp)
        elif auth_resp.status_code > 500:
            raise JumpCloudServerError(auth_resp)
        else:
            raise JumpCloudUnexpectedResponse(auth_resp)

    def _get_xsrf_token(self):
        if self.xsrf_token is None:
            xsrf_resp = self.http.get("https://console.jumpcloud.com/userconsole/xsrf",
                                      timeout=JumpCloudSession.HTTP_TIMEOUT)
            assert(xsrf_resp.status_code == 200)
            self.xsrf_token = xsrf_resp.json().get("xsrf")
        return self.xsrf_token

    def get_aws_saml_assertion(self, profile):
        assert(self.logged_in)
        aws_resp = self.http.get(profile.jumpcloud_url)
        assert(aws_resp.status_code == 200)
        assert("SAMLResponse" in aws_resp.text)
        return self._extract_saml_response(aws_resp.text)

    def _extract_saml_response(self, html):
        soup = BeautifulSoup(html, "lxml")
        tag = soup.find("input", attrs={'name': "SAMLResponse"})
        assert(tag is not None)
        saml_response_b64 = tag.attrs['value']
        saml_response = base64.b64decode(saml_response_b64)
        return saml_response


class JumpCloudError(Exception):
    def __init__(self, message, resp):
        Exception.__init__(self, message)
        self.message = message
        self.response = resp
        try:
            self.jumpcloud_error_message = resp.json().get("error")
        except JSONDecodeError:
            self.jumpcloud_error_message = None


class JumpCloudServerError(JumpCloudError):
    def __init__(self, resp):
        message = f"JumpCloud returned HTTP {resp.status_code} server error"
        JumpCloudError.__init__(self, message, resp)


class JumpCloudAuthFailure(JumpCloudError):
    def __init__(self, resp=None):
        message = "JumpCloud authentication failed. Check your username and password and try again."
        JumpCloudError.__init__(self, message, resp)


class JumpCloudMFARequired(JumpCloudError):
    def __init__(self, resp):
        message = "Multi-factor authentication is required on your JumpCloud account."
        JumpCloudError.__init__(self, message, resp)


class JumpCloudMFAFailure(JumpCloudError):
    def __init__(self, resp):
        message = "Multi-factor authentication failed. Check your MFA token and try again."
        JumpCloudError.__init__(self, message, resp)


class JumpCloudUnexpectedResponse(JumpCloudError):
    """Indicates a response that we weren't expecting, i.e. that JumpCloud
    changed their auth workflow or we didn't reverse-engineer it properly."""
    def __init__(self, resp):
        message = f"JumpCloud returned unexpected HTTP {resp.status_code} response"
        JumpCloudError.__init__(self, message, resp)
