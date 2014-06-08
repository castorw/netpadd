import time
import sqlalchemy
from sqlalchemy.orm import relationship
from ctrdn.netpadd import database
from ctrdn.netpadd.monitor import DeviceProbe
from ctrdn.netpadd.probe.util import ping

__author__ = 'Lubomir Kaplan <castor@castor.sk>'


class PingResult(database.DeclarativeBase):
    __tablename__ = "np_ping_result"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    poll_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("np_monitor_poll.id"), nullable=False)
    address_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("np_core_address.id"), nullable=False)
    pings_min = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    pings_max = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    pings_avg = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    execution_time = sqlalchemy.Column(sqlalchemy.Float, nullable=False)
    error_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    error_message = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    ping_times = relationship("PingTime", backref="np_ping_time.ping_result_id")


class PingTime(database.DeclarativeBase):
    __tablename__ = "np_ping_time"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    ping_result_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("np_ping_result.id"), nullable=False)
    response_time = sqlalchemy.Column(sqlalchemy.Float, nullable=True)


class Probe(DeviceProbe):
    _default_count = None
    _default_timeout = None
    _default_address = None

    def __init__(self, config):
        DeviceProbe.__init__(self, config, "probe-ping")

        assert self._config.get("probe_ping", "default-count"), "no default ping count configured"
        assert self._config.get("probe_ping", "default-timeout"), "no default timeout count configured"
        assert self._config.get("probe_ping", "default-address"), "no default address count configured"
        self._default_count = self._config.getint("probe_ping", "default-count")
        self._default_timeout = self._config.getint("probe_ping", "default-timeout")
        self._default_address = self._config.get("probe_ping", "default-address")

    def poll_device(self, db_session, poll_record, device, probe_name, probe_config):
        ip_result_list = []
        if probe_config["PingAddress"] == "all":
            for address in device.addresses:
                ip_result_list.append(self._perform_ping(address, device, probe_config))
        else:
            self._logger.error("invalid configuration for device %d(%s)", device.id, device.hostname)

        for result in ip_result_list:
            result_record = PingResult()
            result_record.poll_id = poll_record.id
            result_record.address_id = result["Address"].id
            result_record.error_id = None if result["Status"] != 0 else result["Error"]["Id"]
            result_record.error_message = None if result["Status"] != 0 else result["Error"]["Message"]
            result_record.execution_time = result["ExecutionTime"]
            result_record.pings_avg = result["Result"]["Average"] if result["Status"] == 1 else None
            result_record.pings_min = result["Result"]["Min"] if result["Status"] == 1 else None
            result_record.pings_max = result["Result"]["Max"] if result["Status"] == 1 else None
            db_session.add(result_record)
            db_session.flush()
            if result["Status"] == 1:
                for ping_time in result["Result"]["PingTimes"]:
                    ping_time_record = PingTime()
                    ping_time_record.ping_result_id = result_record.id
                    ping_time_record.response_time = ping_time
                    db_session.add(ping_time_record)

    def _perform_ping(self, address, device, probe_config):
        if address.enabled:
            if address.ip_version == 4:
                result = self._perform_ipv4_ping(address.address, int(probe_config["PingCount"]), int(probe_config["PingTimeout"]))
            else:
                self._logger.error("unsupported address version %d for ping probe, device=%d(%s)", address.ip_version,
                                   device.id, device.hostname)
                result = dict(Status=0, Error=dict(Id="UNSUPPORTED_ADDRESS_VERSION",
                                                   Message="unsupported address version " + str(address.ip_version)),
                              ExecutionTime=0)
        else:
            result = dict(Status=0, Error=dict(Id="ADDRESS_DISABLED",
                                               Message="not polling disabled address"),
                          ExecutionTime=0)

        result["Address"] = address
        return result

    def _perform_ipv4_ping(self, host, count, timeout):
        result_list = []
        start_time = time.time()

        # perform pings
        for i in range(0, count):
            result = ping.do_one(host, timeout)
            result_list.append(result)
        end_time = time.time()

        # calculate min time, max time, avg time
        pt_min = None
        pt_max = None
        for result in (x for x in result_list if x):
            pt_min = result if pt_min is None or pt_min > result else pt_min
        for result in (x for x in result_list if x):
            pt_max = result if pt_max is None or pt_max < result else pt_max
        pt_avg_sum = 0
        pt_avg_count = 0
        for result in (x for x in result_list if x):
            pt_avg_sum += result
            pt_avg_count += 1
        pt_avg = None if pt_avg_count == 0 else pt_avg_sum/pt_avg_count

        ping_result = dict(PingTimes=result_list,
                           Max=pt_max, Min=pt_min, Average=pt_avg)
        self._logger.debug("processed pings for address=%s, count=%d/%d, time=%f",
                           host, pt_avg_count, count, end_time-start_time)
        if pt_avg_count < 1:
            return dict(Status=0, Error=dict(Id="NO_RESPONSES_RECEIVED", Message="no responses received"),
                        ExecutionTime=end_time-start_time)
        else:
            return dict(Status=1, Result=ping_result, ExecutionTime=end_time-start_time)

    def validate_configuration(self, device, probe_config):
        update_config = False
        if not "PingCount" in probe_config:
            self._logger.warn("no PingCount in ping probe configuration for device %s", device.id)
            probe_config["PingCount"] = self._default_count
            update_config = True
        if not "PingTimeout" in probe_config:
            self._logger.warn("no PingTimeout in ping probe configuration for device %s", device.id)
            probe_config["PingTimeout"] = self._default_timeout
            update_config = True
        if not "PingAddress" in probe_config:
            self._logger.warn("no PingAddress in ping probe configuration for device %s", device.id)
            probe_config["PingAddress"] = self._default_address
            update_config = True

        if update_config is True:
            self._logger.warn("fixed ping probe configuration for device %s", device.id)
            return probe_config

        return None


def get_probe_name():
    return "ping"


def get_probe_description():
    return "ICMP Ping Probe"


def get_probe_version():
    return "1.0.0"