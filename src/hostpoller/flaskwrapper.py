"""
Module to wrap and manage flask instance
"""
import json
import logging
from typing import Callable, Generator, List, Tuple

import pandas
from flask import Flask, redirect, render_template, request, url_for
from plotly import graph_objects
from plotly import utils as plotly_utils
from plotly.subplots import make_subplots
from sqlalchemy import distinct, func
from werkzeug import Response


class FlaskWrapper:
    """
    Wrapper for flask service
    """

    def __init__(
        self,
        app_meta: dict,
        table: object,
    ) -> None:
        self.table = table
        self.logger = logging.getLogger(__name__)
        self.flask_app = Flask(
            app_meta["name"],
            static_url_path="/public",
            static_folder="./public",
            template_folder="templates",
        )
        self.flask_app.config["JSON_SORT_KEYS"] = False
        self.requests: dict = {}
        self.listen_ip = app_meta["listen_ip"]
        self.listen_port = app_meta["listen_port"]
        self.logger.info("Initializing FlaskWrapper")
        self.endpoints = []

    def start(self, endpoints: list) -> None:
        """
        Serve flask app on acquired host and port
        """
        for endpoint in endpoints:
            self.endpoints.append(endpoint)
            self.add_endpoint(
                endpoint["name"],
                endpoint["path"],
                endpoint["handler"],
                endpoint["methods"],
            )
        self.flask_app.run(debug=False, host=self.listen_ip, port=self.listen_port)
        self.logger.info(dir(self.flask_app))

    def add_endpoint(
        self, name: str, path: str, handler: Callable, methods: list
    ) -> None:
        """
        Add route to flask app for given path, methods and handler
        """
        self.flask_app.add_url_rule(path, name, handler, methods=methods)

    def yield_results(
        self, template_file: str, message: str, **kwargs: dict
    ) -> Generator:
        """Yield rendered html template"""
        yield f"<pre>{message}</pre>"
        yield render_template(template_file, **kwargs)

    def doc_root(self) -> Response:
        """Redirect / requests to dashboard"""
        return redirect(url_for("dashboard"))

    def dashboard_endpoint(self) -> Tuple:
        """Dashboard endpoint"""
        host_selection = request.args.get("host_selection")
        return_code = 200

        host_list = []
        if self.table.engine.session.is_active:
            table_hosts = self.table.engine.session.query(
                distinct(self.table.response_log.c.host)
            )
            for host in table_hosts:
                host_list.append(host[0])

        if not host_selection:

            return (
                render_template(
                    "host_selection.html",
                    title="Target host selector",
                    post_action="/dashboard",
                    host_list=host_list,
                ),
                return_code,
            )

        # Set layout for subplots
        fig = make_subplots(
            rows=3,
            cols=1,
            subplot_titles=[
                "Response Codes",
                "Last 200 Response Times",
                "Response Log",
            ],
            specs=[[{"type": "xy"}], [{"type": "scatter"}], [{"type": "table"}]],
        )

        # Add plot for response codes
        host_meta = self.evaluate_host_status(host_selection)
        fig.add_trace(
            graph_objects.Bar(
                name="count",
                x=["Invocation Error", "1xx", "2xx", "3xx", "4xx", "5xx"],
                y=[
                    host_meta["return_status"]["Invocation Error"],
                    host_meta["return_status"]["1xx"],
                    host_meta["return_status"]["2xx"],
                    host_meta["return_status"]["3xx"],
                    host_meta["return_status"]["4xx"],
                    host_meta["return_status"]["5xx"],
                ],
            ),
            row=1,
            col=1,
        )

        fig.update_yaxes(title_text="Count", row=1, col=1)
        fig.update_xaxes(title_text="Response Series", row=1, col=1)

        # Add plot for response timing
        timing_ms = self.evaluate_response_times(host_selection)
        fig.add_trace(graph_objects.Scatter(y=timing_ms, name="ms"), row=2, col=1)
        fig.update_xaxes(title_text="Invocation Count", row=2, col=1)
        fig.update_yaxes(title_text="Time(ms)", row=2, col=1)

        # Add plot for response logs
        log_query = self.table.engine.session.query(
            self.table.response_log.c.response_date,
            self.table.response_log.c.host,
            self.table.response_log.c.request_path,
            self.table.response_log.c.response_code,
            self.table.response_log.c.response_reason,
        ).filter(self.table.response_log.c.host == host_selection)

        df_table = pandas.read_sql_query(
            log_query.statement, self.table.engine.session.bind
        )
        fig.add_trace(
            graph_objects.Table(
                header=dict(
                    values=[
                        "Date",
                        "Hostname",
                        "Request Path",
                        "Response Code",
                        "Response Reason",
                    ],
                    font=dict(size=10),
                    align="left",
                ),
                cells=dict(
                    values=[df_table[k].tolist() for k in df_table.columns],
                    align="left",
                ),
            ),
            row=3,
            col=1,
        )

        # Update subplot layout
        fig.update_layout(height=800, showlegend=False, hovermode="x")

        subplots = json.dumps(fig, cls=plotly_utils.PlotlyJSONEncoder)

        return (
            render_template(
                "dashboard.html",
                host=host_selection,
                host_list=host_list,
                post_action="/dashboard",
                subplots=subplots,
            ),
            return_code,
        )

    def evaluate_host_status(self, host_selection) -> dict:
        """
        Collect response values for given host selection
        """
        host_meta = {}
        host_meta["name"] = host_selection
        host_meta["return_status"] = {
            "Invocation Error": 0,
            "1xx": 0,
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
        }
        for result in self.table.engine.session.query(
            distinct(self.table.response_log.c.response_code)
        ).filter(self.table.response_log.c.host == host_selection):
            status_count = self.table.engine.session.query(
                func.count(self.table.response_log.c.response_code)
            ).filter(
                self.table.response_log.c.host == host_selection,
                self.table.response_log.c.response_code == result[0],
            )
            for count in status_count:
                return_code = result[0]
                if return_code < 100:
                    host_meta["return_status"]["Invocation Error"] = count[0]
                elif 100 <= return_code < 200:
                    host_meta["return_status"]["1xx"] = count[0]
                elif 200 <= return_code < 300:
                    host_meta["return_status"]["2xx"] = count[0]
                elif 300 <= return_code < 400:
                    host_meta["return_status"]["3xx"] = count[0]
                elif 400 <= return_code < 500:
                    host_meta["return_status"]["4xx"] = count[0]
                elif 500 <= return_code < 600:
                    host_meta["return_status"]["5xx"] = count[0]
                else:
                    self.logger.error("Unhandled status: %s", result[0])
        return host_meta

    def evaluate_response_times(self, host_selection: str) -> List:
        """
        Evaluate response times for given host selection
        """
        timing_ms = []
        timing_query = (
            self.table.engine.session.query(self.table.response_log.c.time_elapsed)
            .filter(self.table.response_log.c.host == host_selection)
            .limit(200)
        )

        df_timing = pandas.read_sql_query(
            timing_query.statement, self.table.engine.session.bind
        )
        timing = [df_timing[key].tolist() for key in df_timing.columns]

        for time in timing[0]:
            timing_ms.append(int(int(time) / 1000))

        return timing_ms
