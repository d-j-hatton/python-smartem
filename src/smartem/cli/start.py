import argparse
import os
import subprocess
from pathlib import Path

import yaml


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--data",
        help="Directory where database wil be initialised",
        dest="data_dir",
    )
    args = parser.parse_args()

    credentials_file = os.getenv("SMARTEM_CREDENTIALS")
    if not credentials_file:
        raise AttributeError(
            "No credentials file specified for smartem database (environment variable SMARTEM_CREDENTIALS)"
        )
    with open(credentials_file, "r") as stream:
        creds = yaml.safe_load(stream)
    os.environ["PGPASSWORD"] = creds["password"]

    server_start = subprocess.run(
        [
            "pg_ctl",
            "-D",
            args.data_dir,
            "-l" f"{Path(args.data_dir) / 'logfile'}",
            "start",
        ]
    )
    if server_start.returncode:
        exit(
            f"FATAL: Database server failed to start with return code {server_start.returncode}"
        )
