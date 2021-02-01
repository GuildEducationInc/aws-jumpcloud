from collections import namedtuple

from bs4 import BeautifulSoup  # pylint: disable=E0401

SAMLRole = namedtuple("SAMLRole", ["role_arn", "principal_arn"])


def get_assertion_roles(saml_assertion_xml):
    # Returns a list of AWS roles that the assertion says may be assumed.
    soup = BeautifulSoup(saml_assertion_xml, "lxml-xml")
    assertion_tag = soup.find("Assertion")
    assert assertion_tag is not None
    attr_tags = assertion_tag.find_all(
        "Attribute", attrs={"Name": "https://aws.amazon.com/SAML/Attributes/Role"}
    )
    saml_roles = []
    assert len(attr_tags) > 0
    for attr_tag in attr_tags:
        value_tag = attr_tag.find("AttributeValue")
        assert value_tag is not None
        text = value_tag.text
        role_arn, principal_arn = text.split(",")
        assert role_arn.startswith("arn:aws:iam::")
        assert principal_arn.startswith("arn:aws:iam::")
        saml_roles.append(SAMLRole(role_arn, principal_arn))
    return saml_roles


def get_assertion_duration(saml_assertion_xml):
    # Returns the SAML assertion's SessionDuration attribute, in seconds.
    soup = BeautifulSoup(saml_assertion_xml, "lxml-xml")
    assertion_tag = soup.find("Assertion")
    assert assertion_tag is not None
    attr_tag = assertion_tag.find(
        "Attribute",
        attrs={"Name": "https://aws.amazon.com/SAML/Attributes/SessionDuration"},
    )
    if attr_tag is None:
        return None
    else:
        value_tag = attr_tag.find("AttributeValue")
        assert value_tag is not None
        return int(value_tag.text)
