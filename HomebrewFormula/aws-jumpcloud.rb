class AwsJumpcloud < Formula
  include Language::Python::Virtualenv

  desc "aws-vault like tool for JumpCloud authentication"
  homepage "https://github.com/GuildEducationInc/aws-jumpcloud"
  url "https://github.com/GuildEducationInc/aws-jumpcloud/archive/2.0.0.tar.gz"
  sha256 "d500b6115d1d32d60f6a29668961286414bbcf22d9d2550bbcf90bd49ea23d36"
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
