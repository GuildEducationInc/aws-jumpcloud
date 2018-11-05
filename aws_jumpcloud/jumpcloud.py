import base64
import json

from bs4 import BeautifulSoup  # pylint: disable=E0401
from requests import Session as HTTPSession


class JumpCloudSession(object):
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.http = HTTPSession()
        self.logged_in = False

    def login(self):
        xsrf_resp = self.http.get("https://console.jumpcloud.com/userconsole/xsrf")
        assert(xsrf_resp.status_code == 200)
        xsrf_token = xsrf_resp.json().get("xsrf")

        data = {"email": self.email, "password": self.password}
        headers = {'Content-Type': 'application/json',
                   'X-Requested-With': 'XMLHttpRequest',
                   'X-Xsrftoken': xsrf_token}
        auth_resp = self.http.post("https://console.jumpcloud.com/userconsole/auth",
                                   headers=headers, data=json.dumps(data))
        assert(auth_resp.status_code == 200)
        self.logged_in = True

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
