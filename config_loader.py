import os
from pathlib import Path

import yaml


def load_config(config_path: Path = Path('config.yaml')) -> dict:
    """
    Load config.yaml and merge with environment variables.

    SMTP credentials are always read from environment variables,
    never from the config file — this keeps credentials out of
    version control even if someone accidentally commits config.yaml
    with filled-in values.

    Raises FileNotFoundError if config.yaml is missing.
    Raises KeyError if EMAIL_USERNAME or EMAIL_PASSWORD are not set.

    Returns the config dict with smtp.username and smtp.password
    populated from environment variables.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    config['smtp']['username'] = os.environ['EMAIL_USERNAME']
    config['smtp']['password'] = os.environ['EMAIL_PASSWORD']

    # EMAIL_TO overrides the recipients list when set — used by GitHub Actions
    # so the real destination address stays out of the committed config file.
    if os.environ.get('EMAIL_TO'):
        config['email']['to'] = [os.environ['EMAIL_TO']]

    return config


def validate_config(config: dict) -> None:
    """
    Validate required config keys are present.
    Raise ValueError with a clear message if anything is missing.
    Required: smtp.host, smtp.port, smtp.username, smtp.password,
              email.to (non-empty list), analysis.error_rate_threshold
    """
    smtp = config.get('smtp', {})
    for key in ('host', 'port', 'username', 'password'):
        if not smtp.get(key):
            raise ValueError(f"Missing required config: smtp.{key}")

    email_cfg = config.get('email', {})
    if not email_cfg.get('to'):
        raise ValueError("Missing required config: email.to (must be a non-empty list)")

    analysis = config.get('analysis', {})
    if 'error_rate_threshold' not in analysis:
        raise ValueError("Missing required config: analysis.error_rate_threshold")
