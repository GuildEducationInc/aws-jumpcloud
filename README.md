# aws-jumpcloud

Allows you to authenticate with AWS using your JumpCloud credentials. Based on ideas from [aws-vault](https://github.com/99designs/aws-vault), [aws-okta](https://github.com/segmentio/aws-okta/), and [jumpcloud_aws](https://github.com/synaptic-cl/jumpcloud_aws).

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

### via [Homebrew](https://brew.sh/)

:warn: **As of February 2019, Homebrew distributes a [broken version of `virtualenv`](https://github.com/Homebrew/brew/pull/5697#issuecomment-462516958). That means this formula won't install, so skip ahead to the manual installation instructions for now.**

TODO: Give it a few weeks and check to see if this works. Stafford researched more about the issue and it traces back to [this setuptools issue](https://github.com/pypa/setuptools/issues/1642#issuecomment-457648989).

~`brew tap GuildEducationInc/aws-jumpcloud https://github.com/GuildEducationInc/aws-jumpcloud.git`~

~`brew install aws-jumpcloud`~

### Manual

Prerequisite: Python 3.6 or newer.

If you're running macOS but don't have Python 3, I recommend installing it with [Homebrew](https://brew.sh/). The command `brew install python` will install it without breaking your existing Python installation.

To install `aws-jumpcloud` itself, just point `pip3` at the latest GitHub release:
```bash
$ pip3 install https://github.com/GuildEducationInc/aws-jumpcloud/archive/1.2.0.tar.gz
```

### Migrating from `~/.aws` credentials

If you were previously using persistent credentials in `~/.aws/config`, here are some tips for moving to JumpCloud SSO:
* Since you won't be using those persistent credentials, remove that file when installing `aws-jumpcloud`.
* If you've been setting `AWS_DEFAULT_PROFILE` in your `~/.bash_profile` (or equivalent), you should stop setting that, since you're not using the standard AWS config file
* On the other hand, since AWS profiles point to a specific region, you'll probably want to add `AWS_DEFAULT_REGION` to your `~/.bash_profile` (or equivalent). (`export AWS_DEFAULT_REGION=us-west-1`, for example.)
* If nothing else is using the IAM access keys previously in your `~/.aws/config`, disable or delete the access keys from the [IAM Console](https://console.aws.amazon.com/iam/home#/users). From that page you can search for the access key itself, or browse/search by username.


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
Enter the JumpCloud SSO URL for duff: <url copied from the JumpCloud Console>
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


### Exporting credentials into your environment

It's a small hassle to put `aws-jumpcloud exec profile` before every AWS-related command that you run. The `aws-jumpcloud export` command displays the `export` commands that will load your temporary AWS credentials directly into your shell. This will let you run AWS commands directly from the shell, although it won't recognize when your temporary credentials have expired.

If you're not using multi-factor authentication, you can put a command like this into your `.bash_profile` to load the AWS into every shell:

```bash
eval "$(aws-jumpcloud export duff)"
```

If you use multi-factor authentication, the command needs to be a little more complicated. Before callling `aws-jumpcloud` you must first make sure you have active AWS credentials for the given profile. The two-step dance is necessary because we can't safely prompt for your MFA token when output isn't going to stdout, as is the case with `$()`.

```bash
aws-jumpcloud exec duff -- true && eval "$(aws-jumpcloud export duff)"
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

## Contributing

aws-jumpcloud is open-source and licensed under the [MIT License](LICENSE).

Use the project's [GitHub Issues feature](https://github.com/GuildEducationInc/aws-jumpcloud/issues) to report bugs and make feature requests.

Even better, if you're able to write code yourself to fix bugs or implement new features, [submit a pull request on GitHub](https://github.com/GuildEducationInc/aws-jumpcloud/pulls) which will help us move the software forward much faster.
