# MailWatch

MailWatch is a small daemon that watches a mailbox on a mail server over IMAP. It idles on the INBOX folder and processes new (unseen) messages — logging each message's recipient, date, and size as structured JSON, and moving messages whose configured `matches` callback returns true (by default the subject is searched for `Testing Mailwatch`) to the Junk folder. It shuts down gracefully on `SIGINT` (Ctrl+C) or `SIGTERM`, closing the IMAP connection before exiting.

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
