{
  pkgs,
  mailwatchModule,
  mailwatchPackage,
}:
let
  dovecot = pkgs.dovecot;
  doveadm = "${dovecot}/bin/doveadm";

  cert = pkgs.runCommand "mailwatch-test-cert" { nativeBuildInputs = [ pkgs.openssl ]; } ''
    mkdir -p "$out"
    openssl req -x509 -newkey rsa:2048 -keyout "$out/key.pem" -out "$out/cert.pem" \
      -days 3650 -nodes -subj "/CN=mailwatch.test"
    chmod 600 "$out/key.pem"
  '';

  sendJunk = pkgs.writeShellScriptBin "send-junk" ''
    { printf 'From: spammer@gmail.com\nTo: alice@localhost\nSubject: ppd.nvim plugin spam\n\nBuy this thing.'; } \
      | ${doveadm} save -u alice
  '';

  sendHam = pkgs.writeShellScriptBin "send-ham" ''
    { printf 'From: colleague@example.com\nTo: alice@localhost\nSubject: Weekly team update\n\nNothing to see here.'; } \
      | ${doveadm} save -u alice
  '';
in
{
  name = "mailwatch";

  nodes.machine =
    { ... }:
    {
      imports = [ mailwatchModule ];

      services.dovecot2 = {
        enable = true;
        enablePAM = true;
        settings = {
          dovecot_config_version = dovecot.version;
          dovecot_storage_version = dovecot.version;
          mail_driver = "maildir";
          mail_path = "maildir:~/Maildir";
          protocols = [ "imap" ];
          ssl_server_cert_file = "${cert}/cert.pem";
          ssl_server_key_file = "${cert}/key.pem";
        };
      };

      users.users.alice = {
        isNormalUser = true;
        initialPassword = "foobar";
      };

      security.pki.certificateFiles = [ "${cert}/cert.pem" ];

      services.mailwatch = {
        enable = true;
        package = mailwatchPackage;
        settings = {
          host = "127.0.0.1";
          port = 993;
          username = "alice";
          password = "foobar";
        };
      };

      environment.systemPackages = [
        sendJunk
        sendHam
      ];

      system.stateVersion = "26.11";
    };

  testScript = ''
    import datetime

    start_all()

    machine.wait_for_unit("dovecot.service")
    machine.wait_for_unit("mailwatch.service")

    machine.succeed("${doveadm} mailbox create -u alice Junk || true")

    machine.succeed("send-ham")
    machine.wait_until_succeeds(
        'test "$(${doveadm} search -u alice mailbox INBOX | wc -l)" -eq 1',
        timeout=datetime.timedelta(seconds=120),
    )

    machine.succeed("send-junk")
    machine.wait_until_succeeds(
        'test "$(${doveadm} search -u alice mailbox Junk | wc -l)" -eq 1',
        timeout=datetime.timedelta(seconds=120),
    )
    machine.succeed(
        'test "$(${doveadm} search -u alice mailbox INBOX | wc -l)" -eq 1'
    )
  '';
}