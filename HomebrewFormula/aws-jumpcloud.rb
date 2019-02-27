class AwsJumpcloud < Formula
  include Language::Python::Virtualenv

  desc "aws-vault like tool for JumpCloud authentication"
  homepage "https://github.com/GuildEducationInc/aws-jumpcloud"
  url "https://github.com/GuildEducationInc/aws-jumpcloud/archive/1.2.1.tar.gz"
  sha256 "350251bed4fc059dabb8107b9d4e49352caed6a544d5286b8facbbbf1e428349"
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
