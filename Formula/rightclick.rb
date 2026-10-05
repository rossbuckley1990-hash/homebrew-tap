class Rightclick < Formula
  desc "Install an app. Your AI learns what it can do"
  homepage "https://github.com/rossbuckley1990-hash/rightclick"
  url "https://github.com/rossbuckley1990-hash/rightclick/releases/download/v0.1.1/rightclick-0.1.1-source.tar.gz"
  sha256 "5e34b08b18c20710867e3c22bda46020dc86f0e3cfaacf899945b1aa53467335"
  license "Apache-2.0"

  bottle do
    root_url "https://github.com/rossbuckley1990-hash/homebrew-tap/releases/download/rightclick-0.1.1"
    sha256 cellar: :any_skip_relocation, arm64_tahoe: "35f4b9b8a6f206d9673ac4391d85d3bf13b050ba884adb37c1322e4a5400ac7c"
  end

  depends_on arch: :arm64
  depends_on macos: :sonoma
  uses_from_macos "swift" => :build, since: :sonoma

  def select_free_command_line_tools
    developer = Pathname("/Library/Developer/CommandLineTools")
    return unless (developer/"usr/bin/swift").exist?

    ENV["DEVELOPER_DIR"] = developer.to_s
    ENV["SDKROOT"] = (developer/"SDKs/MacOSX.sdk").to_s
    ENV.prepend_path "PATH", developer/"usr/bin"
    ENV["CC"] = (developer/"usr/bin/clang").to_s
    ENV["CXX"] = (developer/"usr/bin/clang++").to_s
  end

  def fetch
    select_free_command_line_tools
    compiler = Utils.safe_popen_read("swift", "--version")[/Swift version ([0-9.]+)/, 1]
    if !compiler || Version.new(compiler) < Version.new("6.2")
      odie "Source builds require Swift 6.2+ from the free Apple Command Line Tools."
    end
    # SwiftPM's manifest sandbox cannot nest inside Homebrew's build sandbox.
    # Homebrew still confines the build; its fetch phase permits dependencies.
    system "swift", "package", "--disable-sandbox", "--force-resolved-versions", "resolve"
  end

  def install
    select_free_command_line_tools
    ENV["ZERO_AR_DATE"] = "1"
    system "swift", "build", "--product", "rightclick", *std_swift_args,
           "--disable-sandbox", "--force-resolved-versions", "--skip-update",
           "-Xswiftc", "-debug-prefix-map", "-Xswiftc", "#{buildpath}=/rightclick",
           "-Xswiftc", "-file-prefix-map", "-Xswiftc", "#{buildpath}=/rightclick",
           "-Xcc", "-fdebug-prefix-map=#{buildpath}=/rightclick",
           "-Xcc", "-ffile-prefix-map=#{buildpath}=/rightclick",
           "-Xlinker", "-oso_prefix", "-Xlinker", "#{buildpath}/"
    bin.install ".build/release/rightclick"
    (pkgshare/"ThirdPartyLicenses").install Dir["packaging/ThirdPartyLicenses/*"]
  end

  test do
    assert_equal version.to_s, shell_output("#{bin}/rightclick version").strip
    text = JSON.parse(shell_output("#{bin}/rightclick inspect 'RightClick' --json"))
    assert_equal "text", text.fetch("kind")
    assert_equal "RightClick", text.fetch("text")
    assert_equal "public.plain-text", text.fetch("typeIdentifier")
    assert_equal 10, text.fetch("byteCount")
  end
end
