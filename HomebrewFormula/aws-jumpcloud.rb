class AwsJumpcloud < Formula
  include Language::Python::Virtualenv

  desc "aws-vault like tool for JumpCloud authentication"
  homepage "https://github.com/CirrusMD/aws-jumpcloud"
  url "{{tarball_url}}"
  version "{{version}}"
  sha256 "{{sha256}}"
  head "https://github.com/CirrusMD/aws-jumpcloud.git", :branch => 'main'
  depends_on "python@3.8"

  def install
    venv = virtualenv_create(libexec, "python3")
    system libexec/"bin/pip3", "install", "-v", "--ignore-installed", buildpath
    system libexec/"bin/pip3", "uninstall", "-y", "aws-jumpcloud"
    venv.pip_install_and_link buildpath
  end

  def caveats; <<~EOS
    Use aws-jumpcloud --help to see available commands

    Check out the README to look into migrating existing ~/.aws credentials:

      https://github.com/CirrusMD/aws-jumpcloud/blob/main/README.md#migrating-from-aws-credentials

  EOS
  end

  test do
    assert_match "rotate", shell_output("#{bin}/aws-jumpcloud help")
  end
end
