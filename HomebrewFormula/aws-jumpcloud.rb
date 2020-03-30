class AwsJumpcloud < Formula
  include Language::Python::Virtualenv

  desc "aws-vault like tool for JumpCloud authentication"
  homepage "https://github.com/Tomer20/aws-jumpcloud"
  url "https://github.com/Tomer20/aws-jumpcloud/archive/2.1.6.tar.gz"
  sha256 "aa4862780070837f7ca986277fc4b96ba8722c14392502ba1e696f83a88c30bc"
  head "https://github.com/Tomer20/aws-jumpcloud.git", :branch => 'master'
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

      https://github.com/Tomer20/aws-jumpcloud#migrating-from-aws-credentials

  EOS
  end

  test do
    assert_match "rotate", shell_output("#{bin}/aws-jumpcloud help")
  end
end
