import time
from ctrdn.netpadd.monitor import DeviceProbe
from ctrdn.netpadd.probe.util import ping

__author__ = 'Lubomir Kaplan <castor@castor.sk>'


class Probe(DeviceProbe):
    _default_count = None
    _default_timeout = None
    _default_address = None

    def __init__(self, config, db):
        DeviceProbe.__init__(self, config, db, "probe-ping")

        assert self._config.get("probe_ping", "default-count"), "no default ping count configured"
        assert self._config.get("probe_ping", "default-timeout"), "no default timeout count configured"
        assert self._config.get("probe_ping", "default-address"), "no default address count configured"
        self._default_count = self._config.getint("probe_ping", "default-count")
        self._default_timeout = self._config.getint("probe_ping", "default-timeout")
        self._default_address = self._config.get("probe_ping", "default-address")

    def poll_device(self, device, probe_name, probe_config):
        ip_result_list = []
        if probe_config["PingAddress"] == "all":
            for address_index, address in enumerate(device["IpAddress"]):
                ip_result_list.append(self._perform_ping(address, device, probe_config))
        elif type(probe_config["PingAddress"]) == list:
            for address_index, address in enumerate(probe_config["PingAddress"]):
                address = device["IpAddress"][address_index]
                ip_result_list.append(self._perform_ping(address, device, probe_config))
        else:
            self._logger.error("invalid configuration for device %s", device["_id"])

        return dict(PerAddress=ip_result_list)

    def _perform_ping(self, address, device, probe_config):
        if address["Version"] == 4:
            result = self._perform_ipv4_ping(address["Address"], probe_config["PingCount"], probe_config["PingTimeout"])
        else:
            self._logger.error("unsupported address version %d for ping probe, device=%s", address["Version"],
                               device["_id"])
            result = dict(Status=0, Error=dict(Id="UNSUPPORTED_ADDRESS_VERSION",
                                               Message="Unsupported address version " + str(address["Version"])))

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
        pt_avg = 0 if pt_avg_count == 0 else pt_avg_sum/pt_avg_count

        ping_result = dict(ExecutionTime=end_time-start_time, PingTimes=result_list,
                           Max=pt_max, Min=pt_min, Average=pt_avg)
        self._logger.debug("processed pings for address=%s, count=%d/%d, time=%f",
                           host, pt_avg_count, count, end_time-start_time)
        if pt_avg_count < 1:
            return dict(Status=0, Error=dict(Id="NO_RESPONSES_RECEIVED", Message="no responses received"))
        else:
            return dict(Status=1, Result=ping_result)

    def validate_configuration(self, device, probe_config):
        update_config = False
        if not "PingCount" in probe_config:
            self._logger.warn("no PingCount in ping probe configuration for device %s", device["_id"])
            probe_config["PingCount"] = self._default_count
            update_config = True
        if not "PingTimeout" in probe_config:
            self._logger.warn("no PingTimeout in ping probe configuration for device %s", device["_id"])
            probe_config["PingTimeout"] = self._default_timeout
            update_config = True
        if not "PingAddress" in probe_config:
            self._logger.warn("no PingAddress in ping probe configuration for device %s", device["_id"])
            probe_config["PingAddress"] = self._default_address
            update_config = True

        if update_config is True:
            self._logger.warn("fixed ping probe configuration for device %s", device["_id"])
            return probe_config

        return None


def get_probe_name():
    return "ping"


def get_probe_description():
    return "ICMP Ping Probe"


def get_probe_version():
    return "1.0.0"