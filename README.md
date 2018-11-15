# aws-jumpcloud

Allows you to authenticate with AWS using your GitHub credentials. Based on ideas from [aws-vault](https://github.com/99designs/aws-vault), [aws-okta](https://github.com/segmentio/aws-okta/), and [jumpcloud_aws](https://github.com/synaptic-cl/jumpcloud_aws).

### Features

* Uses your JumpCloud account to authenticate to Amazon Web Services, via SAML single sign-on (SSO), and retrieves a set of temporary AWS security credentials.
* Uses the native OS keychain to store JumpCloud credentials and AWS temporary IAM credentials. Built atop [Keyring](https://pypi.org/project/keyring/) for Python, with support for macOS, Windows, and Linux.
* Supports multiple AWS profiles, to handle multiple AWS integrations in your JumpCloud account.
* Supports JumpCloud multi-factor authentication; prompts you for your MFA code when needed.

### Why a new tool just for JumpCloud?

* Adding SAML support to `aws-vault` would be a big project.
* `aws-okta` doesn't look amenable to adding a second identity provider -- not to mention, it would go against the name.
* `jumpcloud_aws` was broken when I tried to use it. It also didn't support MFA or more than one integration.
* There are also a few other tools on GitHub which might work well, I didn't tried all of them.


## Installation

Prerequisite: Python 3.6 or newer.

To install direct from GitHub:
```bash
$ pip3 install https://github.com/GuildEducationInc/aws-jumpcloud/archive/v1.0.0.tar.gz
```

If you've downloaded the release from GitHub, just point `pip3` at the archive:
```bash
$ pip3 install v1.0.0.tar.gz
```


## Usage

Context-sensitive help is available for every command in `aws-jumpcloud`.

```
# Show general help about aws-jumpcloud
$ aws-jumpcloud --help

# Show the most detailed information about the exec command
$ aws-jumpcloud exec --help
```

### Adding a profile

Typically you'll start by adding a profile for your primary AWS integration. This will prompt you for the JumpCloud URL, which you can grab from the [JumpCloud Console](https://console.jumpcloud.com) in your browser. Right-click on any AWS integration icon and choose "Copy Link Address."

```
$ aws-jumpcloud add duff
Enter the JumpCloud SSO URL for duff: https://sso.jumpcloud.com/saml2/aws
Profile duff added.
```

### Listing profiles

You can view all profiles registered in your `aws-jumpcloud` keychain:

```
$ aws-jumpcloud list

Profile           AWS Account       AWS Role     IAM session expires    
================  ================  ===========  =====================
duff              <unknown>         <unknown>    <no active session>    
```

### Running a command

Once you've created a profile, you can use it to run a command, like `aws s3 ls`.

The first time you login to JumpCloud, you will be prompted for your JumpCloud email and password, along with an MFA token if necessary. `aws-jumpcloud` will store your email and password in your OS keychain for future logins, but you'll be prompted for the MFA token every time.

```
$ aws-jumpcloud exec duff -- aws s3 ls
Enter your JumpCloud email address: duffman@duff-beer.com
Enter your JumpCloud password: 
JumpCloud login details saved in your OS keychain.
Enter your JumpCloud multi-factor auth code: 798708
Attempting SSO authentication to Amazon Web Services...


2018-11-14 17:09:32 duff-logs-us-east-1
2018-11-13 10:40:21 duff-data-backup
```

Behind the scenes, `aws-jumpcloud` has used SAML single sign-on to authenticate with Amazon Web Services and request a set of temporary security credentials. The temporary credentials are cached in your operating system's keychain for an hour, so you can continue to run AWS commands without needing to authenticate again.

```
$ aws-jumpcloud exec duff -- aws s3 ls s3://duff-logs-us-east-1/
2018-11-14 18:19:50        557 2018-11-15-01-19-49-793C97002B9C598F
2018-11-14 18:19:57        461 2018-11-15-01-19-56-800F45BFB3E1F93B
2018-11-14 18:20:08        462 2018-11-15-01-20-07-819FA67DCE9E7DE2
```


### Rotating credentials

After a profile's temporary IAM credentials expire, `aws-jumpcloud` will automatically delete the credentials from its keychain. New temporary credentials will automatically be requested the next time you attempt to use that profile. However, you can also rotate the credentials at any time and request new credentials immediately.

```
$ aws-jumpcloud rotate duff
Temporary IAM session for duff removed.
Using JumpCloud login details from your OS keychain.
Enter your JumpCloud multi-factor auth code: 788149
Attempting SSO authentication to Amazon Web Services...

AWS temporary session rotated; new session valid until Thu Nov 15 20:49:38 2018 UTC.
```

### Removing profiles

You can remove a profile if you no longer need it:

```
$ aws-jumpcloud remove duff
Profile duff and temporary IAM session removed.
```

And you can clear `aws-jumpcloud`'s entire keychain if necessary:

```
$ aws-jumpcloud remove --all

All configuration profiles, temporary IAM sessions, and JumpCloud login
credentials have been removed from your OS keychain.
```


## Developing

```
$ pip install -r test-requirements.txt
$ pycodestyle *.py aws_jumpcloud/
$ pylint -E *.py aws_jumpcloud/
```

## Copyright

Copyright &copy; 2018, Guild Education, Inc. All rights reserved.

11/15/2018: Waiting for approval to release this as open-source. If we do, include contribution instructions and a license here.
