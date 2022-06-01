import argparse
import os
import secrets
import string
import subprocess
from pathlib import Path

import yaml

from smartem.data_model import setup


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--data",
        help="Directory where database wil be initialised",
        dest="data_dir",
    )
    parser.add_argument(
        "--port",
        help="Port the database server will serve, default is 5432",
        dest="port",
        default=5432,
    )
    parser.add_argument(
        "--make-credentials-file",
        help="Make a credentials file for the database for use by smartem, default is True",
        dest="make_creds",
        default=True,
    )
    args = parser.parse_args()

    alphabet = string.ascii_letters + string.digits
    pswd_su = "".join(secrets.choice(alphabet) for i in range(20))

    with open(".postgres_pwd.txt", "w") as pwdfile:
        pwdfile.write(pswd_su)

    initdb_cmd = [
        "initdb",
        "-A",
        "md5",
        "-D",
        args.data_dir,
        "--pwfile=.postgres_pwd.txt",
    ]
    initdb = subprocess.run(initdb_cmd)
    Path(".postgres_pwd.txt").unlink()
    if initdb.returncode:
        exit(f"Database initialisation failed with return code {initdb.returncode}")
    else:
        print("Database initialisation complete")

        os.environ["PGPASSWORD"] = pswd_su

        server_start = subprocess.run(
            [
                "pg_ctl",
                "-o",
                f'"-p {args.port}"',
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

        if args.make_creds:
            creds = {
                "username": os.getenv("USER"),
                "password": pswd_su,
                "host": "localhost",
                "port": args.port,
                "database": "smartem",
            }
            with open(Path(args.data_dir) / "credentials.yaml", "w") as credfile:
                yaml.dump(creds, credfile)

        create_db = subprocess.run(["createdb", "smartem"])
        if create_db.returncode:
            exit(
                f"FATAL: smartem database was not created with return code {server_start.returncode}"
            )

        os.environ["SMARTEM_CREDENTIALS"] = str(
            (Path(args.data_dir) / "credentials.yaml").resolve()
        )
        setup()

        subprocess.run(["pg_ctl", "-D", args.data_dir, "stop"])

        print(
            f"Run the following to setup database access credentials:\n export SMARTEM_CREDENTIALS={(Path(args.data_dir) / 'credentials.yaml').resolve()}"
        )
