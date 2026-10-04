{
  defaultPackage,
}:
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.mailwatch;

  # Settings the application requires. Any of them may instead be supplied
  # through the environment file, or through an explicit `MAILWATCH_*`
  # variable in `environment`, e.g. when the value is a secret.
  requiredSettings = [
    "host"
    "username"
    "password"
  ];
in
{
  options.services.mailwatch = {
    enable = lib.mkEnableOption "MailWatch mailbox watcher";

    package = lib.mkOption {
      type = lib.types.package;
      default = defaultPackage.${pkgs.stdenv.hostPlatform.system}.default;
      defaultText = lib.literalMD "the `default` package of the flake providing this module";
      description = "The MailWatch package to use.";
    };

    settings = {
      host = lib.mkOption {
        type = lib.types.nullOr lib.types.nonEmptyStr;
        default = null;
        example = "imap.example.com";
        description = "Mail server hostname.";
      };

      port = lib.mkOption {
        type = lib.types.nullOr (lib.types.ints.between 1 65535);
        default = null;
        example = 993;
        description = ''
          Mail server IMAP port.

          If null, the application default of 993 is used.
        '';
      };

      username = lib.mkOption {
        type = lib.types.nullOr lib.types.nonEmptyStr;
        default = null;
        example = "user@example.com";
        description = "Username used to log in to the mail server.";
      };

      password = lib.mkOption {
        type = lib.types.nullOr lib.types.nonEmptyStr;
        default = null;
        description = ''
          Password used to log in to the mail server.

          This value is written to the world-readable Nix store. Prefer
          {option}`services.mailwatch.environmentFile` to keep the password
          out of the store.
        '';
      };
    };

    extraArgs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [
        "--port"
        "1993"
      ];
      description = ''
        Additional command-line arguments passed to `mailwatch`.

        Command-line flags take precedence over environment variables, which
        take precedence over {option}`services.mailwatch.settings`.
      '';
    };

    environment = lib.mkOption {
      type = lib.types.attrsOf lib.types.str;
      default = { };
      example = {
        SSL_CERT_FILE = "/etc/ssl/certs/ca-certificates.crt";
      };
      description = ''
        Additional environment variables for the service.

        These take precedence over variables derived from
        {option}`services.mailwatch.settings`, but are overridden by
        {option}`services.mailwatch.environmentFile`.

        Values set here are stored in the systemd unit file in the Nix store;
        use {option}`services.mailwatch.environmentFile` for secrets.
      '';
    };

    environmentFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      example = "/run/secrets/mailwatch.env";
      description = ''
        Path to a systemd environment file supplying `MAILWATCH_*` variables,
        for example `MAILWATCH_PASSWORD=...`. Values from this file take
        precedence over {option}`services.mailwatch.settings` and
        {option}`services.mailwatch.environment`.

        The file is read by the service manager (PID 1) before the service
        sandbox is set up, so it only needs to be readable by root; the
        service user does not need access to it.

        Use an absolute runtime path (e.g. a decrypted secret). A Nix path
        literal such as `./mailwatch.env` would be copied into the
        world-readable Nix store.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    warnings = lib.lists.optional (cfg.settings.password != null) ''
      services.mailwatch.settings.password is stored in the world-readable
      Nix store and in the systemd unit file. Prefer
      services.mailwatch.environmentFile to keep the password out of the
      store.
    '';

    assertions = lib.lists.map (name: {
      assertion =
        cfg.settings.${name} != null
        || cfg.environmentFile != null
        || builtins.hasAttr "MAILWATCH_${lib.strings.toUpper name}" cfg.environment;
      message = ''
        services.mailwatch requires one of the following to be set:
        services.mailwatch.settings.${name},
        services.mailwatch.environment."MAILWATCH_${lib.strings.toUpper name}",
        or services.mailwatch.environmentFile.
      '';
    }) requiredSettings;

    systemd.services.mailwatch = {
      description = "MailWatch mailbox watcher";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];

      environment =
        (lib.attrsets.filterAttrs (_: v: v != null) {
          MAILWATCH_HOST = cfg.settings.host;
          MAILWATCH_PORT = if cfg.settings.port == null then null else toString cfg.settings.port;
          MAILWATCH_USERNAME = cfg.settings.username;
          MAILWATCH_PASSWORD = cfg.settings.password;
        })
        // cfg.environment;

      serviceConfig = {
        ExecStart = lib.strings.escapeShellArgs ([ "${cfg.package}/bin/mailwatch" ] ++ cfg.extraArgs);
        EnvironmentFile = lib.lists.optional (cfg.environmentFile != null) cfg.environmentFile;

        DynamicUser = true;
        Restart = "on-failure";
        RestartSec = 5;
        # Exponential restart backoff so that a long IMAP outage does not
        # produce a permanent restart storm: the delay starts at RestartSec
        # and doubles with each restart, capped at RestartMaxDelaySec.
        RestartSteps = 6;
        RestartMaxDelaySec = "5min";
        UMask = "0077";

        NoNewPrivileges = true;
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ProtectClock = true;
        ProtectControlGroups = true;
        ProtectHostname = true;
        ProtectKernelLogs = true;
        ProtectKernelModules = true;
        ProtectKernelTunables = true;
        ProtectProc = "invisible";
        ProcSubset = "pid";

        CapabilityBoundingSet = "";
        LockPersonality = true;
        MemoryDenyWriteExecute = true;
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
          "AF_INET6"
        ];
        RestrictNamespaces = true;
        RestrictRealtime = true;
        RestrictSUIDSGID = true;
        SystemCallArchitectures = "native";
        SystemCallFilter = [ "@system-service" ];
        SystemCallErrorNumber = "EPERM";
      };
    };
  };
}
