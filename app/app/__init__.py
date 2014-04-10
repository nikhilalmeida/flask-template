import elasticsearch
from app import config
import logging
from logging.handlers import RotatingFileHandler
from statsd import StatsClient




class Context(object):
    """Context object initializes logging and config"""

    def __init__(self,  logfile=None, loglevel=logging.INFO):
        """Initializes the context. Initializes logging.
        Args:

        """
        # initialize_logging(log_filename=logfile, log_level=loglevel)
        hosts = ["{}:{}".format(host.strip(), config.ES_PORT)for host in config.ES_HOSTS]
        self.es = elasticsearch.Elasticsearch(hosts, sniff_on_start=True,
                                      sniff_on_connection_fail=True, sniffer_timeout=60)

        self.stats_client = StatsClient(config.STATSD_HOST, config.STATSD_PORT, prefix="dupecheck_tool")

        # self.handler = RotatingFileHandler('logs/decision_tool.log', maxBytes=10000, backupCount=1)
        # self.handler.setLevel(logging.INFO)

    def add_logger(self, logger):
        self.logger = logger

context = Context()

