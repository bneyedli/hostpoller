#!/usr/bin/env python3
"""
Module to poll host for a given period and frequency and store results
"""

import logging
from argparse import Namespace as ArgNamespace
from datetime import datetime
from threading import Thread
from time import sleep, time
from typing import Any, Dict, Generator

import requests
from dateutil import parser as date_parser
from flaskwrapper import FlaskWrapper
from parseargs import ParseArgs
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout as RequestsReadTimeout
from sqlalchemy import Column, Integer, String, Table, Text
from squeal import Squeal
from trapper import Trapper

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s:%(name)s:%(levelname)s]: %(message)s",
)


class ResponseLog:  # pylint: disable=too-few-public-methods
    """
    Initialize table and provide interface to SQLAlchemy wrapper
    """

    def __init__(self, engine_type: str, engine_uri: str) -> None:
        squeal_engine = {
            "type": f"{engine_type}",
            "file_path": f"{engine_uri}?check_same_thread=False",
        }
        self.engine = Squeal(squeal_engine)
        self.meta_data = self.engine.meta_data
        self.response_log = Table(
            "response_log",
            self.meta_data,
            Column("id", Integer, primary_key=True),
            Column("response_date", Text),
            Column("protocol", String),
            Column("host", String),
            Column("request_path", String),
            Column("response_code", Integer),
            Column("response_reason", String),
            Column("response_cookies", String),
            Column("response_headers", String),
            Column("time_elapsed", String),
            extend_existing=True,
        )
        self.access_log_meta = self.engine.meta_data.tables["response_log"]
        self.meta_data.create_all(self.engine.engine)


class Poller:
    """
    Interface to poll given target and record results
    """

    def __init__(self, parsed_args: ArgNamespace, table: ResponseLog) -> None:
        self.table = table
        if parsed_args.target.endswith("/"):
            self.target = parsed_args.target
        else:
            self.target = parsed_args.target + "/"

        self.target_meta = {
            "protocol": self.target.split(":")[0],
            "host": self.target.split("/")[2],
            "path": "/" + self.target.split("/", 3)[3],
            "monitor_period": parsed_args.monitor_period,
            "polling_frequency": parsed_args.polling_frequency,
            "request_timeout": parsed_args.request_timeout,
        }

    def start(self) -> None:
        """
        Poll target and record results
        """
        responses = self.poll_target()

        for response in responses:
            squeal_record = {
                "response_date": response["response_date"],
                "protocol": self.target_meta["protocol"],
                "host": self.target_meta["host"],
                "request_path": self.target_meta["path"],
                "response_code": response["status_code"],
                "response_reason": str(response["status_reason"]),
                "response_cookies": str(response["cookies"]),
                "response_headers": str(response["headers"]),
                "time_elapsed": str(response["time_elapsed"]),
            }

            self.table.engine.insert(self.table.response_log, squeal_record)

    def poll_target(self) -> Generator:
        """
        Loop until timeout make request and yield responses
        """
        time_start = int(time())
        time_stop = time_start + self.target_meta["monitor_period"]
        if self.target_meta["monitor_period"] == 0:
            logger.info("Polling target indefinitely")
        else:
            logger.info(
                "Polling target for %s seconds", self.target_meta["monitor_period"]
            )
        while True:
            request_response = self.make_request()

            if self.target_meta["monitor_period"] == 0:
                logger.debug("Running indefinitiely")
            else:
                if int(time()) >= time_stop:
                    break
            sleep(self.target_meta["polling_frequency"])
            yield request_response

    def make_request(self) -> Dict:
        """
        Make a single request for given host and protocol and store and return response
        """
        response_meta = {}  # type: Dict[str, Any]
        logger.debug("Making request to %s", self.target)
        response_meta["cookies"] = None
        response_meta["headers"] = None
        response_meta["status_code"] = 1
        response_meta["time_elapsed"] = 0
        try:
            request_result = requests.get(
                self.target,
                timeout=self.target_meta["request_timeout"],
            )
        except RequestsConnectionError as err:
            logger.debug("Connection error")
            if err.args[0].reason.args:
                response_meta["status_reason"] = err.args[0].reason.args[0]
            else:
                response_meta["status_reason"] = str(err)
            response_meta["response_date"] = datetime.utcnow().isoformat()
        except RequestsReadTimeout as err:
            logger.debug("Read Timeout: %s", err)
            response_meta[
                "status_reason"
            ] = f"Read Timeout after {self.target_meta['request_timeout']}s"
            response_meta["response_date"] = datetime.utcnow().isoformat()
        except Exception as err:
            logger.error("Unhandled exception: %s", err)
            raise SystemExit from err
        else:
            response_meta["status_code"] = request_result.status_code
            response_meta["status_reason"] = request_result.reason
            response_meta["cookies"] = request_result.cookies
            response_meta["headers"] = request_result.headers
            response_meta["response_date"] = date_parser.parse(
                request_result.headers["date"]
            ).isoformat()
            response_meta["time_elapsed"] = request_result.elapsed.microseconds
        return response_meta


if __name__ == "__main__":
    trapper = Trapper()
    app_metadata = {
        "name": "hostpoller",
        "description": "Monitor host and store results.",
    }
    app_arguments = [
        {
            "switch": "--target",
            "default": "https://127.0.0.1/",
            "help": "Host or ip to target and path, default: https://127.0.0.1/",
            "type": str,
        },
        {
            "switch": "--monitor-period",
            "default": 10,
            "help": "Time in seconds to monitor host, 0 will run forever default: 10",
            "type": int,
        },
        {
            "switch": "--polling-frequency",
            "default": 1,
            "help": "Time in seconds to poll given host over specified period, default: 1",
            "type": float,
        },
        {
            "switch": "--request-timeout",
            "default": 10,
            "help": "Timeout for requests to target, default: 10",
            "type": int,
        },
        {
            "switch": "--listen-ip",
            "default": "127.0.0.1",
            "help": "Web listener binding ip, default: 127.0.0.1",
            "type": str,
        },
        {
            "switch": "--listen-port",
            "default": 9000,
            "help": "Web listener binding port, default: 9000",
            "type": int,
        },
        {
            "switch": "--sql-engine",
            "default": "sqlite",
            "help": "SQL Engine, default: sqlite",
            "type": str,
        },
        {
            "switch": "--sql-db-path",
            "default": f"{app_metadata['name']}.db",
            "help": f"SQL Engine, default: {app_metadata['name']}.db",
            "type": str,
        },
    ]

    parser = ParseArgs(app_metadata["name"], app_metadata["description"], app_arguments)
    args = parser.args_parsed

    response_log = ResponseLog(args.sql_engine, args.sql_db_path)

    logger.info(
        "Targeting %s every %ss",
        args.target,
        args.polling_frequency,
    )

    poller = Poller(args, response_log)

    logger.info("Starting poller")
    poller_thread = Thread(target=poller.start, daemon=True)
    poller_thread.start()

    flask_meta = {
        "name": app_metadata["name"],
        "listen_ip": args.listen_ip,
        "listen_port": args.listen_port,
    }
    flask_app = FlaskWrapper(
        flask_meta,
        response_log,
    )

    flask_endpoints = [
        {
            "path": "/",
            "name": "doc_root",
            "handler": flask_app.doc_root,
            "methods": ["GET"],
        },
        {
            "path": "/dashboard",
            "name": "dashboard",
            "handler": flask_app.dashboard_endpoint,
            "methods": ["GET", "POST"],
        },
    ]

    logger.info("Starting flask")
    flask = Thread(target=flask_app.start, args=(flask_endpoints,))
    flask.daemon = True
    flask.start()

    while True:
        if flask.is_alive():
            sleep(1)
        else:
            break
