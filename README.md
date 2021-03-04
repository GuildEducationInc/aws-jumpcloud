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
* There are also a few other tools on GitHub which might work well, I didn't try all of them.


## Installation

### via [Homebrew](https://brew.sh/)

```bash
brew tap CirrusMD/aws-jumpcloud https://github.com/CirrusMD/homebrew-aws-jumpcloud.git
brew install aws-jumpcloud
```

### Manual

Prerequisite: Python 3.8 or newer.

If you're running macOS but don't have Python 3, I recommend installing it with [Homebrew](https://brew.sh/). The command `brew install python` will install it without breaking your existing Python installation.

Grab the latest release .pex package from [this repo](https://github.com/CirrusMD/aws-jumpcloud/releases)
```
curl -L -O https://github.com/CirrusMD/aws-jumpcloud/releases/download/v2.1.8/aws_jumpcloud-macos-<VERSION>.pex
#ex: curl -L -O https://github.com/CirrusMD/aws-jumpcloud/releases/download/v2.1.8/aws_jumpcloud-macos-2.1.8.pex
```

Make the pex file executable: 
```
chmod 0755 aws_jumpcloud-macos-<VERSION>.pex
#ex: chmod 0755 aws_jumpcloud-macos-2.1.8.pex
```

Run it!
```
./aws_jumpcloud-macos-<VERSION>.pex
#ex: ./aws_jumpcloud-macos-2.1.8.pex
```

Optionally move it somewhere in your PATH

```
mv ./aws_jumpcloud-macos-<VERSION>.pex /usr/local/bin/aws-jumpcloud
./aws-jumpcloud --version
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

Profile           AWS Account       AWS Role       IAM session expires
================  ================  =============  =====================
duff              544300394404      JumpCloudDevs  <no active session>
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


## Advanced features

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


### Adding a profile with an assumed role

You may find that you need to interact with AWS using a different IAM role than the one connected to JumpCloud. For example, your JumpCloud integration may only grant read-only access to resources in the AWS Console, and you need to assume an expanded role in order to make changes. Or, if your company has more than one AWS account, you may login to a single AWS account, and then assume a role in another account to access the resources in that account.

`aws-jumpcloud` profiles can be configured to automatically assume another IAM role when you establish a session. Each time you establish a new AWS session using such a profiles, `aws-jumpcloud` will login through JumpCloud, and then immediately call the [AssumeRole API](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html) to request credentials for the other role. The role can be in your own AWS account or in another AWS account.

To configure a profile to assume a role on each login, add the `--role` parameter to the `aws-jumpcloud add` command. Here's an example of assuming a role in the same account:

```
$ aws-jumpcloud add --role=deployer duff-deployer
Enter the JumpCloud SSO URL for duff-deployer: <url copied from the JumpCloud Console>
Profile duff-deployer added.
```

You can specify the assumed role by name or ARN, which allows you to assume a role in another AWS account:

```
$ aws-jumpcloud add --role=arn:aws:iam::619893369699:role/deployer subaccount-deployer
Enter the JumpCloud SSO URL for subaccount-deployer: <url copied from the JumpCloud Console>
Profile duff-deployer added.
```

If the role requires an External ID to be provided to the AssumeRole API, that must be specified when creating the `aws-jumpcloud` profile, using the `--external-id` parameter. For example:

```
$ aws-jumpcloud add --role=deployer --external-id=QgbnxwqT2w duff-deployer
Enter the JumpCloud SSO URL for duff-deployer: <url copied from the JumpCloud Console>
Profile duff-deployer added.
```

The AWS IAM User Guide contains [more information about assuming IAM roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use.html).


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

### 1Password support

If the [1Password CLI](https://1password.com/downloads/command-line/) is installed, `aws-jumpcloud` will automatically use your JumpCloud credentials and MFA token from 1Password. The credentials must be stored in an item named `jumpcloud`

#### Initial Setup
To set up the 1Password CLI for the first time, download and install the CLI and run the following commands with your own 1Password information from the emergency kit and correct password.

```bash
$ op signin guild-education first.last@guildeducation.com
Enter the Secret Key for first.last@guildeducation.com at guild-education.1password.com: VERY-SECRET-THING from your emergency kit
Enter the password for first.last@guildeducation.com at guild-education.1password.com: ur1Passwordpassword
```

#### Credential Rotation
To automatically rotate expired credentials for a given profile when you fire up
your shell, add the following to your `.(bash|zsh|whatever)rc`

```bash
aws-jumpcloud-rotate() {
  if [ "$(aws-jumpcloud is-active $1)" != "1" ]; then
    eval $(op signin duff-beer)
    aws-jumpcloud rotate $1
  fi
}

aws-jumpcloud-rotate duff
```

The "duff-beer" refers to the [subdomain](https://support.1password.com/command-line/) of your 1Password acount (e.g., the "duff-beer" of your "duff-beer.1password.com" 1Password account).
You may `export OP_SUBDOMAIN=duff-beer` in your `.(bash|zsh|whatever)rc` to have `aws-jumpcloud` automatically refresh expired 1Password CLI sessions.

To manually rotate credentials from your terminal:

```bash
eval $(op signin duff-beer)
aws-jumpcloud rotate duff
```

## Developing

```
$ python3 setup.py develop
$ pip3 install -r test-requirements.txt
$ black *.py aws_jumpcloud/
```

### Rolling out a new version

1. Update the version number in [version.py](https://github.com/CirrusMD/aws-jumpcloud/blob/main/aws_jumpcloud/version.py)
2. Create a PR to the `main` branch
3. Release maintainer, tag and push the branch with the corresponding tag for the version ex: ```git tag v2.1.8```. Homebrew will automatically update after that. 

## Contributing

aws-jumpcloud is open-source and licensed under the [MIT License](LICENSE).

Use the project's [GitHub Issues feature](https://github.com/CirrusMD/aws-jumpcloud/issues) to report bugs and make feature requests.

Even better, if you're able to write code yourself to fix bugs or implement new features, [submit a pull request on GitHub](https://github.com/CirrusMD/aws-jumpcloud/pulls) which will help us move the software forward much faster.
