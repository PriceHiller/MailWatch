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
  inherit (lib)
    literalExpression
    mkEnableOption
    mkIf
    mkOption
    optional
    optionalAttrs
    types
    ;

  cfg = config.services.mailwatch;
in
{
  options.services.mailwatch = {
    enable = mkEnableOption "MailWatch mailbox watcher";

    package = mkOption {
      type = types.package;
      default = defaultPackage.${pkgs.stdenv.hostPlatform.system}.default;
      defaultText = literalExpression "inputs.mailwatch.packages.${pkgs.stdenv.hostPlatform.system}.default";
      description = "The MailWatch package to use.";
    };

    settings = {
      host = mkOption {
        type = types.str;
        example = "imap.example.com";
        description = "Mail server hostname.";
      };

      port = mkOption {
        type = types.port;
        default = 993;
        description = "Mail server port.";
      };

      username = mkOption {
        type = types.str;
        example = "user@example.com";
        description = "Username used to log in to the mail server.";
      };

      password = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = ''
          Password used to log in to the mail server.

          This value is written to the world-readable Nix store. Prefer
          {option}`services.mailwatch.envFile` to keep the password out of
          the store.
        '';
      };
    };

    envFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      example = "/run/secrets/mailwatch.env";
      description = ''
        Path to a systemd environment file supplying `MAILWATCH_*` variables,
        for example `MAILWATCH_PASSWORD=...`. Values from this file take
        precedence over {option}`services.mailwatch.settings`.
      '';
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.settings.password != null || cfg.envFile != null;
        message = ''
          services.mailwatch requires either services.mailwatch.settings.password
          or services.mailwatch.envFile to be set.
        '';
      }
    ];

    systemd.services.mailwatch = {
      description = "MailWatch mailbox watcher";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];

      environment =
        {
          MAILWATCH_HOST = cfg.settings.host;
          MAILWATCH_PORT = toString cfg.settings.port;
          MAILWATCH_USERNAME = cfg.settings.username;
        }
        // optionalAttrs (cfg.settings.password != null) {
          MAILWATCH_PASSWORD = cfg.settings.password;
        };

      serviceConfig = {
        ExecStart = "${cfg.package}/bin/mailwatch";
        EnvironmentFile = optional (cfg.envFile != null) cfg.envFile;

        DynamicUser = true;
        Restart = "on-failure";
        RestartSec = 5;

        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
      };
    };
  };
}