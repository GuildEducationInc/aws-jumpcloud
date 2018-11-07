import base64
import json

from bs4 import BeautifulSoup  # pylint: disable=E0401
from requests import Request as HTTPRequest, Session as HTTPSession


class JumpCloudSession(object):
    HTTP_TIMEOUT = 5

    def __init__(self, email, password, otp_required=False):
        self.email = email
        self.password = password
        self.otp_required = otp_required
        self.http = HTTPSession()
        self.logged_in = False
        self.xsrf_token = None

    def login(self):
        assert(not self.logged_in)
        headers = {'Content-Type': 'application/json',
                   'X-Requested-With': 'XMLHttpRequest',
                   'X-Xsrftoken': self._get_xsrf_token()}
        data = {"email": self.email, "password": self.password}
        if self.otp_required:
            data['otp'] = input("Multi-factor authentication code: ").strip()
        auth_resp = self.http.post("https://console.jumpcloud.com/userconsole/auth",
                                   headers=headers, json=data, allow_redirects=False,
                                   timeout=JumpCloudSession.HTTP_TIMEOUT)
        if auth_resp.status_code == 200:
            self.logged_in = True
            return
        elif auth_resp.status_code == 302 and "error=4014" in auth_resp.headers['Location']:
            if self.otp_required:
                raise JumpCloudMFAFailure(auth_resp)
            else:
                self.otp_required = True
                self.login()
        elif auth_resp.status_code == 401:
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

    def get_aws_saml_assertion(self):
        # TODO: Try using this with more than one AWS integration (the multi-
        # role code hasn't been tested)
        assert(self.logged_in)
        aws_resp = self.http.get("https://sso.jumpcloud.com/saml2/aws")
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
        self.response = resp


class JumpCloudServerError(JumpCloudError):
    def __init__(self, resp):
        message = f"JumpCloud returned HTTP {resp.status_code} server error"
        JumpCloudError.__init__(self, message, resp)


class JumpCloudAuthFailure(JumpCloudError):
    def __init__(self, resp=None):
        message = "JumpCloud authentication failed. Check your username and password and try again."
        if resp and resp.headers['Content-Type'] == 'application/json':
            data = resp.json()
            if "error" in data:
                message = data['error']
        JumpCloudError.__init__(self, message, resp)


class JumpCloudMFAFailure(JumpCloudError):
    def __init__(self, resp):
        message = "Multi-factor authentication failed. Check your MFA token and try again."
        JumpCloudError.__init__(self, message, resp)


class JumpCloudUnexpectedResponse(JumpCloudError):
    # Indicates a response that we weren't expecting, i.e. that JumpCloud
    # changed their auth workflow or we didn't reverse-engineer it properly.
    def __init__(self, resp):
        message = f"JumpCloud returned unexpected HTTP {resp.status_code} response"
        JumpCloudError.__init__(self, message, resp)
