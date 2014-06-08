import ConfigParser
from Queue import Queue
import importlib
import logging
from os import listdir
from time import sleep
from os.path import isfile, join
from ctrdn.netpadd.constants import NetPadConstants
from ctrdn.netpadd.database import NetPadDatabase
from ctrdn.netpadd.monitor import PollingPlanner, DevicePoller


__author__ = 'Lubomir Kaplan <castor@castor.sk>'
__version__ = "1.0.0"


class NetPadDaemon():
    _config = None
    _database = None
    _planner = None
    _logger = logging.getLogger("daemon")
    _poller_threads = []

    def __init__(self, config):
        self._config = config
        """:type : ConfigParser.ConfigParser"""

        assert self._config.get("monitor", "queue-max-size"), "queue-max-size invalid of not found in config"
        assert self._config.get("monitor", "threads"), "threads invalid of not found in config"
        assert self._config.getint("monitor", "threads") > 0 or self._config.getint("monitor", "threads") <= \
                                                                NetPadConstants.MONITOR_MAX_POLLER_THREADS, \
            "thread count defined in config is invalid, thread count must in range <1;20>"
        assert self._config.get("monitor", "probe-path"), "no probe path specified in configuration file"

        self._logger.info("NetPadDaemon v" + __version__ + " by " + __author__)

    def start(self):
        self._logger.info("starting up")

        # import available probes
        probes_path = self._config.get("monitor", "probe-path")
        probe_files = [f for f in listdir(probes_path) if isfile(join(probes_path, f))]
        probe_modules = []
        for probe_file in probe_files:
            if probe_file.startswith("probe_") and probe_file.endswith(".py"):
                probe_class_name = probes_path.replace("/", ".") + "." + probe_file.replace(".py", "")
                probe_modules.append(importlib.import_module(probe_class_name))
                self._logger.debug("importing probe " + probe_class_name)
        for module in probe_modules:
            self._logger.info("imported probe " + module.get_probe_name() +
                              " (" + module.get_probe_description() + ") v" + module.get_probe_version())

        self._database = NetPadDatabase(self._config)

        # create polling queue
        poll_queue = Queue(self._config.getint("monitor", "queue-max-size"))
        self._logger.debug("created device polling queue, maxsize=%d", poll_queue.maxsize)

        # start device poller threads
        polling_thread_count = self._config.getint("monitor", "threads")
        for i in range(0, polling_thread_count):
            poller = DevicePoller(i, self._config, self._database.get_session_maker(), probe_modules, poll_queue)
            poller.setDaemon(True)
            poller.start()
            self._poller_threads.append(poller)
        self._logger.debug("started %d device polling threads", polling_thread_count)

        # start polling planner
        self._planner = PollingPlanner(self._config, self._database.get_session_maker(), poll_queue)
        self._planner.setDaemon(True)
        self._planner.start()

        while True:
            try:
                sleep(1)
            except KeyboardInterrupt:
                self._logger.warning("quitting")
                sleep(1)
                quit()


def _process_error(message, e):
    msg = "[ERROR] " + message
    print(msg)
    print("-"[:1] * len(msg))
    print(e)


def main():
    try:
        config = ConfigParser.ConfigParser()
        config.read(NetPadConstants.CONFIGURATION_FILE_NAME)
        logging.basicConfig(level=config.get("logging", "level"),
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        daemon = NetPadDaemon(config)
        daemon.start()
    except ConfigParser.ParsingError as e:
        _process_error("Unable to load NetPadDaemon configuration", e)


if __name__ == "__main__":
    main()