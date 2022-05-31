import argparse
import os
import subprocess

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

    server_stop = subprocess.run(["pg_ctl", "-D", args.data_dir, "stop"])
    if server_stop.returncode:
        exit(
            f"FATAL: Database server failed to stop with return code {server_stop.returncode}"
        )
