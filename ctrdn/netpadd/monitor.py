import abc
import logging
import threading
from ConfigParser import ConfigParser
from Queue import Queue
import time
from pymongo.database import Database

from ctrdn.netpadd.constants import NetPadConstants

__author__ = 'Lubomir Kaplan <castor@castor.sk>'


class DeviceProbe:
    _logger = None
    _db = None
    _config = None

    def __init__(self, config, db, short_name):
        self._logger = logging.getLogger(short_name)
        self._db = db
        """:type : Database"""
        self._config = config
        """:type : ConfigParser"""

    @abc.abstractmethod
    def poll_device(self, device, probe_name, probe_config):
        return None


class DevicePollerException(Exception):
    pass


class DevicePoller(threading.Thread):
    _logger = None
    _thread_id = None
    _poll_queue = None
    _probes = None
    _db = None
    _config = None

    def __init__(self, thread_id, config, db, probes, poll_queue):
        threading.Thread.__init__(self)
        self._probes = probes

        self._thread_id = thread_id
        self._logger = logging.getLogger("poller-{0}".format(self._thread_id))
        self._poll_queue = poll_queue
        """:type : Queue"""

        self._db = db
        """:type : Database"""

        self._config = config
        """:type : ConfigParser"""

        assert isinstance(poll_queue, Queue), "poll_queue is not instance of Queue"
        assert isinstance(db, Database), "db is not instance of Database"
        assert isinstance(config, ConfigParser), "config is not instance of ConfigParser"
        assert 0 <= self._thread_id < NetPadConstants.MONITOR_MAX_POLLER_THREADS, "invalid thread id"

    def run(self):
        self._logger.debug("started device poller thread, id=%d", self._thread_id)
        got_task = False
        while True:
            while not self._poll_queue.empty():
                device = self._poll_queue.get()
                got_task = True
                self._poll_device(device)
                self._poll_queue.task_done()
            if got_task:
                self._logger.debug("waiting for device polling requests")
                got_task = False
            time.sleep(1)

    def _poll_device(self, device):
        device_time_start = time.time()
        probe_stats_dict = {}
        probe_result_dict = {}
        poll_record_id = self._db.np.monitor.poll.insert({})
        for probe_name, probe_config in device["MonitorConfiguration"]["Probes"].iteritems():
            probe_module = None
            for module in self._probes:
                if module.get_probe_name() == probe_name:
                    probe_module = module
                    break

            if not probe_module:
                self._logger.error("unknown probe %s", probe_name)
            else:
                poll_start_time = time.time()
                poll_success = True
                poll_error = None
                try:
                    probe = probe_module.Probe(self._config, self._db)
                    result = probe.poll_device(device, probe_name, probe_config)
                    probe_result = dict(DeviceId=device["_id"], PollId=poll_record_id, Result=result)
                    self._db.np.monitor.result[probe_module.get_probe_name()].insert(probe_result)
                    probe_result_dict[probe_module.get_probe_name()] = result
                except DevicePollerException as exception:
                    poll_success = False
                    poll_error = exception.message
                poll_end_time = time.time()
                probe_stats = dict(Probe=probe_module.get_probe_name(), Time=poll_end_time - poll_start_time,
                                   Success=poll_success, Error=poll_error)
                probe_stats_dict[probe_module.get_probe_name()] = probe_stats
        device_time_end = time.time()
        device_stats = dict(DeviceId=device["_id"], PollerThreadId=self._thread_id, PollTimestamp=device_time_start,
                            Time=device_time_end - device_time_start, Results=probe_stats_dict)
        self._db.np.monitor.poll.update(dict(_id=poll_record_id), {"$set": device_stats})
        self._db.np.monitor.result_last.update(dict(DeviceId=device["_id"]),
                                               {"$set": dict(DeviceId=device["_id"],
                                                             PollId=poll_record_id,
                                                             Time=device_time_end - device_time_start,
                                                             Results=probe_result_dict)}, upsert=True)


class PollingPlanner(threading.Thread):
    _config = None
    _db = None
    _default_poll_interval = None
    _default_probes = {}
    _poll_queue = None
    _logger = logging.getLogger("planner")

    def __init__(self, config, db, poll_queue):
        threading.Thread.__init__(self)
        assert isinstance(config, ConfigParser), "config is not instance of ConfigParser"
        assert isinstance(poll_queue, Queue), "poll_queue is not instance of Queue"
        assert isinstance(db, Database), "db is not instance of pymongo Collection"

        self._config = config
        """:type : ConfigParser"""
        self._db = db
        """:type : Database"""
        self._poll_queue = poll_queue
        """:type : Queue"""

        assert self._config.get("monitor", "default-poll-interval"), "default-poll-interval not configured"
        self._default_poll_interval = self._config.getint("monitor", "default-poll-interval")
        self._logger.debug("set default poll time to %dms", self._default_poll_interval)

        assert self._config.get("monitor", "default-probes"), "default-probes not configured"
        default_probes_string = self._config.get("monitor", "default-probes")
        default_probes_list = default_probes_string.split(",")
        for default_probe in default_probes_list:
            self._default_probes[default_probe.strip()] = {}
        self._logger.debug("set default probes %s", self._default_probes)

        self._logger.debug("polling planner initialized")

    def check_device_monitor_config(self, device):
        update_monitor_config = False
        if not "MonitorConfiguration" in device:
            self._logger.warn("no monitor configuration for %s", device["_id"])
            monitor_config = dict(PollInterval=self._default_poll_interval)
            update_monitor_config = True
        else:
            monitor_config = device["MonitorConfiguration"]
            if not "PollInterval" in monitor_config:
                self._logger.warn("no poll interval configuration for %s", device["_id"])
                monitor_config["PollInterval"] = self._default_poll_interval
                update_monitor_config = True
            if not "Probes" in monitor_config:
                self._logger.warn("no probes configuration for %s", device["_id"])
                monitor_config["Probes"] = self._default_probes
                update_monitor_config = True

        if update_monitor_config is True:
            self._db.np.core.device.update(dict(_id=device["_id"]), {"$set": {"MonitorConfiguration": monitor_config}})
            self._logger.warn("fixed-up monitor config for device %s", device["_id"])
            return self._db.np.core.device.find_one(dict(_id=device["_id"]))

        return device

    def run(self):
        self._logger.info("starting polling planner")
        while True:
            device_list = self._db.np.core.device.find({"MonitorEnabled": True})
            for device in device_list:
                device = self.check_device_monitor_config(device)
                poll_stats_record = self._db.np.monitor.planner.find_one({"DeviceId": device["_id"]})
                if not poll_stats_record:
                    self._db.np.monitor.planner.insert(
                        dict(DeviceId=device["_id"], LastEnqueueTimestamp=time.time() - 3600))
                    poll_stats_record = self._db.np.monitor.planner.find_one(dict(DeviceId=device["_id"]))

                delta = (time.time() - poll_stats_record["LastEnqueueTimestamp"]) * 1000
                if delta >= device["MonitorConfiguration"]["PollInterval"]:
                    self._logger.debug("enqueuing device %s(%s), delta=%dms",
                                       device['_id'],
                                       device['Hostname'], delta)
                    self._poll_queue.put(device)
                    self._db.np.monitor.planner.update(dict(DeviceId=device["_id"]),
                                                       {"$set": {"LastEnqueueTimestamp": time.time()}})

            time.sleep(NetPadConstants.MONITOR_PLANNER_SLEEP_TIME)