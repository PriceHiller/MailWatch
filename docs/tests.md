# Testing

The test suite uses [pytest](https://docs.pytest.org/):

```bash
uv run pytest
```

The NixOS module is tested end-to-end with NixOS VM tests against a local
Dovecot server: once with credentials in `services.mailwatch.settings`, and
once through `services.mailwatch.environmentFile`:

```bash
nix build .#checks.x86_64-linux.mailwatch-vm .#checks.x86_64-linux.mailwatch-vm-environment-file -L
```
