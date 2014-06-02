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
        probe_config = self._check_configuration(device, probe_name, probe_config)
        ip_result_list = []
        if probe_config["PingAddress"] == "all":
            for address_index, address in enumerate(device["IpAddress"]):
                ip_result_list.append(dict(Address=address_index,
                                           Result=self._perform_ping(address, device, probe_config)))
        elif type(probe_config["PingAddress"]) == list:
                for address_index, address in enumerate(probe_config["PingAddress"]):
                    address = device["IpAddress"][address_index]
                    ip_result_list.append(dict(Address=address_index,
                                          Result=self._perform_ping(address, device, probe_config)))
        else:
            self._logger.error("invalid configuration for device %s", device["_id"])
        return dict(PerAddress=ip_result_list)

    def _perform_ping(self, address, device, probe_config):
        if address["Version"] == 4:
            return self._perform_ipv4_ping(address["Address"], probe_config["PingCount"], probe_config["PingTimeout"])
        else:
            self._logger.error("unsupported address version %d for ping probe, device=%s", address["Version"],
                               device["_id"])

    def _perform_ipv4_ping(self, host, count, timeout):
        result_list = []
        start_time = time.time()
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

        self._logger.debug("processed pings for address=%s, count=%d/%d, time=%f",
                           host, pt_avg_count, count, end_time-start_time)
        return dict(Time=end_time-start_time, Pings=result_list, Max=pt_max,
                    Min=pt_min, Average=pt_avg)

    def _check_configuration(self, device, probe_name, probe_config):
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
            monitor_config = device["MonitorConfiguration"]
            for probe_index, probe in enumerate(monitor_config["Probes"]):
                if probe_index == probe_name:
                    monitor_config["Probes"][probe_index] = probe_config
                    break
            self._db.np.core.device.update(dict(_id=device["_id"]), {"$set": dict(MonitorConfiguration=monitor_config)})
            self._logger.warn("fixed ping probe configuration for device %s", device["_id"])

        return probe_config


def get_probe_name():
    return "ping"


def get_probe_description():
    return "ICMP Ping Probe"


def get_probe_version():
    return "1.0.0"