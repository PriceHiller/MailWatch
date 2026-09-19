# MailWatch

MailWatch is a small daemon that watches a mailbox on a mail server over IMAP and takes actions based upon the messages it receives.

The primary motivation behind this is the shitbag spammers who pull my email from various mailing lists and Git hosting sites where my email address is sitting in the logs.

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)

## Setup

Clone the repository and sync the environment:

```bash
uv sync
```

This creates a virtual environment and installs the project along with its development dependencies.

## Usage

Run MailWatch with `uv run` (or activate the virtual environment first):

```bash
uv run mailwatch --host imap.example.com --username user@example.com --password secret
```

Available options:

| Option       | Description      | Default  |
| ------------ | ---------------- | -------- |
| `--host`     | Mail server host | required |
| `--port`     | Mail server port | `993`    |
| `--username` | Login username   | required |
| `--password` | Login password   | required |

### Environment variables

Every option can also be provided through an environment variable. Command-line flags take precedence over environment variables:

| Option       | Environment variable |
| ------------ | -------------------- |
| `--host`     | `MAILWATCH_HOST`     |
| `--port`     | `MAILWATCH_PORT`     |
| `--username` | `MAILWATCH_USERNAME` |
| `--password` | `MAILWATCH_PASSWORD` |

For example:

```bash
export MAILWATCH_HOST=imap.example.com
export MAILWATCH_USERNAME=user@example.com
export MAILWATCH_PASSWORD=secret
uv run mailwatch
```

Run `uv run mailwatch --help` for the full list of options.

## Testing

See [docs/tests.md](docs/tests.md).
