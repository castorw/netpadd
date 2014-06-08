from abc import abstractmethod
from datetime import datetime
import logging
import os
import threading
from ConfigParser import ConfigParser
from Queue import Queue
import time
import sqlalchemy
from sqlalchemy.orm import relationship, backref
from ctrdn.netpadd import database
from ctrdn.netpadd.constants import NetPadConstants

__author__ = 'Lubomir Kaplan <castor@castor.sk>'


class Poll(database.DeclarativeBase):
    __tablename__ = "np_monitor_poll"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    device_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("np_core_device.id"), nullable=False)
    poll_time = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    poll_timestamp = sqlalchemy.Column(sqlalchemy.TIMESTAMP, server_default=sqlalchemy.text("CURRENT_TIMESTAMP"),
                                       nullable=False)


class DevicePlanning(database.DeclarativeBase):
    __tablename__ = "np_monitor_planning"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    device_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("np_core_device.id"), nullable=False)
    last_enqueue_timestamp = sqlalchemy.Column(sqlalchemy.TIMESTAMP, nullable=False)


class DeviceAddress(database.DeclarativeBase):
    __tablename__ = "np_core_address"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    device_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("np_core_device.id"), nullable=False)
    ip_version = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    address = sqlalchemy.Column(sqlalchemy.String(64), nullable=False)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)
    create_timestamp = sqlalchemy.Column(sqlalchemy.TIMESTAMP, server_default=sqlalchemy.text("CURRENT_TIMESTAMP"),
                                         nullable=False)


class DeviceMonitorConfiguration(database.DeclarativeBase):
    __tablename__ = "np_core_monitor_configuration"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    device_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("np_core_device.id"), nullable=False)
    probe_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    attribute_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    attribute_value = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)


class Device(database.DeclarativeBase):
    __tablename__ = "np_core_device"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    hostname = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    monitor_enabled = sqlalchemy.Column(sqlalchemy.Boolean, default=False, nullable=False)
    create_timestamp = sqlalchemy.Column(sqlalchemy.TIMESTAMP, server_default=sqlalchemy.text("CURRENT_TIMESTAMP"),
                                         nullable=False)
    addresses = relationship("DeviceAddress", backref="np_core_address.device_id")
    plannings = relationship("DevicePlanning", backref="np_monitor_planning.device_id")
    polls = relationship("Poll", backref="np_monitor_poll.device_id")
    monitor_configuration = relationship("DeviceMonitorConfiguration",
                                         backref="np_core_monitor_configuration.device_id")

    def get_monitor_configuration(self, probe_name=None):
        result_dict = dict(__db_objects={})
        for attribute in self.monitor_configuration:
            if attribute.probe_name == probe_name:
                result_dict[attribute.attribute_name] = attribute.attribute_value
                result_dict["__db_objects"][attribute.attribute_name] = attribute
        return result_dict

    def set_monitor_configuration(self, session, configuration, probe_name=None):
        for attribute_name, attribute_value in configuration.items():
            if attribute_name == "__db_objects":
                continue
            if not attribute_name in configuration["__db_objects"]:
                db_object = DeviceMonitorConfiguration()
                db_object.attribute_name = attribute_name
                db_object.attribute_value = attribute_value
                db_object.device_id = self.id
                if not probe_name is None:
                    db_object.probe_name = probe_name
                else:
                    db_object.probe_name = None
            else:
                db_object = configuration["__db_objects"][attribute_name]
                db_object.attribute_value = attribute_value
                db_object.probe_name = probe_name
            session.add(db_object)


class DeviceProbe:
    _logger = None
    _config = None

    def __init__(self, config, short_name):
        self._logger = logging.getLogger(short_name)
        self._config = config
        """:type : ConfigParser"""

    @abstractmethod
    def poll_device(self, db_session, poll_record, device, probe_name, probe_config):
        return None

    @abstractmethod
    def validate_configuration(self, device, probe_config):
        return True


class DevicePoller(threading.Thread):
    _logger = None
    _thread_id = None
    _poll_queue = None
    _probes = None
    _db_session_maker = None
    _config = None

    def __init__(self, thread_id, config, db_session_maker, probes, poll_queue):
        threading.Thread.__init__(self)
        self._probes = probes

        self._thread_id = thread_id
        self._logger = logging.getLogger("poller-{0}".format(self._thread_id))
        self._poll_queue = poll_queue
        """:type : Queue"""

        self._db_session_maker = db_session_maker

        self._config = config
        """:type : ConfigParser"""

        assert isinstance(poll_queue, Queue), "poll_queue is not instance of Queue"
        assert isinstance(config, ConfigParser), "config is not instance of ConfigParser"
        assert 0 <= self._thread_id < NetPadConstants.MONITOR_MAX_POLLER_THREADS, "invalid thread id"

    def run(self):
        pid = os.fork()
        if pid == 0:
            self._logger.debug("started device poller thread, id=%d", self._thread_id)
        else:
            logging.getLogger("threading").debug("started device poller thread, pid=%d", pid)

        got_task = False
        while True:
            while not self._poll_queue.empty():
                device_id = self._poll_queue.get()
                got_task = True
                self._poll_device(device_id)
                self._poll_queue.task_done()
            if got_task:
                self._logger.debug("waiting for device polling requests")
                got_task = False
            time.sleep(1)

    def _poll_device(self, device_id):
        db_session = self._db_session_maker()
        device = db_session.query(Device).get(device_id)
        self._logger.info("polling device %d(%s)", device.id, device.hostname)
        device_time_start = time.time()
        monitor_config = device.get_monitor_configuration()
        poll_record = Poll()
        poll_record.device_id = device_id
        poll_record.poll_timestamp = datetime.now()
        db_session.add(poll_record)
        db_session.flush()
        for probe_name in monitor_config["Core.EnabledProbes"].split(","):
            probe_name = probe_name.strip()
            probe_module = None
            for module in self._probes:
                if module.get_probe_name() == probe_name:
                    probe_module = module
                    probe_config = device.get_monitor_configuration(probe_name)
                    break

            if not probe_module:
                self._logger.error("unknown probe %s", probe_name)
            else:
                # start polling with probe
                probe_instance = probe_module.Probe(self._config, self._db_session_maker)
                """:type : DeviceProbe"""

                # validate configuration for specific probe
                check_result = probe_instance.validate_configuration(device, probe_config)
                if not check_result is None:
                    probe_config = check_result
                    device.set_monitor_configuration(db_session, probe_config, probe_name)

                # perform probing itself
                result = probe_instance.poll_device(db_session, poll_record, device, probe_name, probe_config)

        device_time_end = time.time()
        poll_record.poll_time = device_time_end - device_time_start
        db_session.add(poll_record)
        db_session.commit()
        db_session.close()


class PollingPlanner(threading.Thread):
    _config = None
    _db_session_maker = None
    _default_poll_interval = None
    _default_probes = ""
    _poll_queue = None
    _logger = logging.getLogger("planner")

    def __init__(self, config, db_session_maker, poll_queue):
        threading.Thread.__init__(self)
        assert isinstance(config, ConfigParser), "config is not instance of ConfigParser"
        assert isinstance(poll_queue, Queue), "poll_queue is not instance of Queue"

        self._config = config
        """:type : ConfigParser"""
        self._db_session_maker = db_session_maker
        self._poll_queue = poll_queue
        """:type : Queue"""

        assert self._config.get("monitor", "default-poll-interval"), "default-poll-interval not configured"
        self._default_poll_interval = self._config.getint("monitor", "default-poll-interval")
        self._logger.debug("set default poll time to %dms", self._default_poll_interval)

        assert self._config.get("monitor", "default-probes"), "default-probes not configured"
        default_probes_string = self._config.get("monitor", "default-probes")
        default_probes_list = default_probes_string.split(",")
        for default_probe in default_probes_list:
            if self._default_probes != "":
                self._default_probes += ", "
            self._default_probes += default_probe
        self._logger.debug("set default probes %s", self._default_probes)

        self._logger.debug("polling planner initialized")

    def check_device_monitor_config(self, session, device):
        update_monitor_config = False
        monitor_config = device.get_monitor_configuration()

        if not "Core.PollInterval" in monitor_config:
            self._logger.warn("no poll interval configuration for %s", device.hostname)
            monitor_config["Core.PollInterval"] = self._default_poll_interval
            update_monitor_config = True
        if not "Core.EnabledProbes" in monitor_config:
            self._logger.warn("no probes configuration for %s", device.hostname)
            monitor_config["Core.EnabledProbes"] = self._default_probes
            update_monitor_config = True

        if update_monitor_config is True:
            device.set_monitor_configuration(session, monitor_config)
            self._logger.warn("fixed-up monitor config for device %s", device.hostname)

        return device

    def run(self):
        self._logger.info("starting polling planner")
        while True:
            db_session = self._db_session_maker()
            device_list = db_session.query(Device).filter(Device.monitor_enabled)
            for device in device_list:
                device = self.check_device_monitor_config(db_session, device)
                db_session.commit()
                force_enqueue = False
                if len(device.plannings) < 1:
                    planning = DevicePlanning()
                    planning.device_id = device.id
                    planning.last_enqueue_timestamp = datetime.now()
                    db_session.add(planning)
                    force_enqueue = True
                else:
                    planning = device.plannings[0]
                delta = datetime.now() - planning.last_enqueue_timestamp
                monitor_config = device.get_monitor_configuration()
                if force_enqueue is True or delta.total_seconds() >= int(monitor_config["Core.PollInterval"]):
                    self._logger.debug("enqueuing device %s(%s), delta=%ds",
                                       device.id,
                                       device.hostname, delta.total_seconds())
                    self._poll_queue.put(device.id)
                    planning.last_enqueue_timestamp = datetime.now()
                    db_session.add(planning)
            db_session.commit()
            db_session.close()
            time.sleep(NetPadConstants.MONITOR_PLANNER_SLEEP_TIME)