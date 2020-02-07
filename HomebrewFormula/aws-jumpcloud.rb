class AwsJumpcloud < Formula
  include Language::Python::Virtualenv

  desc "aws-vault like tool for JumpCloud authentication"
  homepage "https://github.com/GuildEducationInc/aws-jumpcloud"
  url "https://github.com/GuildEducationInc/aws-jumpcloud/archive/2.1.3.tar.gz"
  sha256 "2f3c6592ca03b30edc046bfe37049458fce56ff13c4ff5bb18870e0b46325795"
  head "https://github.com/GuildEducationInc/aws-jumpcloud.git", :branch => 'master'
  depends_on "python"

  def install
    venv = virtualenv_create(libexec, "python3")
    system libexec/"bin/pip", "install", "-v", "--ignore-installed", buildpath
    system libexec/"bin/pip", "uninstall", "-y", "aws-jumpcloud"
    venv.pip_install_and_link buildpath
  end

  def caveats; <<~EOS
    Use aws-jumpcloud --help to see available commands

    Check out the README to look into migrating existing ~/.aws credentials:

      https://github.com/GuildEducationInc/aws-jumpcloud#migrating-from-aws-credentials

  EOS
  end

  test do
    assert_match "rotate", shell_output("#{bin}/aws-jumpcloud help")
  end
end
