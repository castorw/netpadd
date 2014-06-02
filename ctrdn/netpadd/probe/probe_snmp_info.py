import json
from pysnmp.entity.rfc3413.oneliner import cmdgen
import time
from ctrdn.netpadd.monitor import DeviceProbe, DevicePollerException

__author__ = 'Lubomir Kaplan <castor@castor.sk>'


class Probe(DeviceProbe):
    _default_snmp_port = None
    _default_snmp_community = None
    _default_snmp_version = None
    _default_snmp_info_dict = None

    def __init__(self, config, db):
        DeviceProbe.__init__(self, config, db, "probe-snmp-info")

        assert self._config.get("probe_snmp_info", "default-snmp-port"), "no default snmp port configured"
        assert self._config.get("probe_snmp_info", "default-snmp-community"), "no default snmp community configured"
        assert self._config.get("probe_snmp_info", "default-snmp-version"), "no default snmp version configured"
        assert self._config.get("probe_snmp_info", "default-snmp-info-dictionary"), "no default snmp info dictionary \
        configured"
        self._default_snmp_port = self._config.getint("probe_snmp_info", "default-snmp-port")
        self._default_snmp_community = self._config.get("probe_snmp_info", "default-snmp-community")
        self._default_snmp_version = self._config.get("probe_snmp_info", "default-snmp-version")
        self._default_snmp_info_dict = json.loads(self._config.get("probe_snmp_info", "default-snmp-info-dictionary"))

    def poll_device(self, device, probe_name, probe_config):
        probe_config = self._check_configuration(device, probe_name, probe_config)
        probe_successful = False
        probe_address_index = 0
        if len(device["IpAddress"]) < 1:
            raise DevicePollerException("no internet protocol address for device %s", device["_id"])

        snmp_data = None
        start_time = time.time()
        snmp_error = None
        while not probe_successful:
            if probe_address_index >= len(device["IpAddress"]):
                self._logger.error("failed to get snmp information from device %s, after trying all addresses",
                                   device["_id"])
                break

            address_record = device["IpAddress"][probe_address_index]
            if address_record["Version"] != 4:
                self._logger.error("unsupported internet protocol version %d for device %s", address_record["Version"],
                                   device["_id"])
                continue

            snmp_error = None
            cmd_generator = cmdgen.CommandGenerator()

            oid_list = []
            oid_name_map = {}
            for name, oid in probe_config["SnmpInfoDictionary"].iteritems():
                oid = oid.encode('ascii', 'ignore')
                oid_list.append(oid)
                oid_name_map[oid] = name

            snmp_err_indication, snmp_err_status, snmp_err_index, snmp_var_binds = cmd_generator.getCmd(
                cmdgen.CommunityData(probe_config["SnmpCommunity"]),
                cmdgen.UdpTransportTarget((address_record["Address"], probe_config["SnmpPort"])), *oid_list)

            if snmp_err_indication:
                snmp_error = str(snmp_err_indication)
            else:
                if snmp_err_status:
                    snmp_error = 'snmp error: %s at %s' % (snmp_err_status.prettyPrint(),
                                 snmp_err_index and snmp_var_binds[-1][int(snmp_err_index) - 1] or '?')
                else:
                    snmp_data = {}
                    for oid, value in snmp_var_binds:
                        mib_name = oid_name_map[oid.prettyOut(oid)]
                        snmp_data[mib_name] = str(value)
                    probe_successful = True

            if not snmp_error is None:
                self._logger.warn("snmp error: %s", snmp_error)

            probe_address_index += 1
        end_time = time.time()

        result_dict = dict(Time=end_time-start_time)
        if snmp_data is None:
            result_dict["Success"] = False
            result_dict["LastError"] = str(snmp_error)
            self._logger.warn("failed to get snmp info, device=%s, time=%f", device["_id"], (end_time-start_time))
        else:
            result_dict["Success"] = True
            result_dict["SnmpData"] = snmp_data
            self._logger.debug("processed snmp info, device=%s, count=%d, time=%f", device["_id"], len(snmp_data),
                               (end_time-start_time))
        return result_dict

    def _check_configuration(self, device, probe_name, probe_config):
        update_config = False
        if not "SnmpVersion" in probe_config:
            self._logger.warn("no SnmpVersion in probe configuration for device %s", device["_id"])
            probe_config["SnmpVersion"] = self._default_snmp_version
            update_config = True
        if not "SnmpCommunity" in probe_config:
            self._logger.warn("no SnmpCommunity in probe configuration for device %s", device["_id"])
            probe_config["SnmpCommunity"] = self._default_snmp_community
            update_config = True
        if not "SnmpPort" in probe_config:
            self._logger.warn("no SnmpPort in probe configuration for device %s", device["_id"])
            probe_config["SnmpPort"] = self._default_snmp_port
            update_config = True
        if not "SnmpInfoDictionary" in probe_config:
            self._logger.warn("no SnmpInfoDictionary in probe configuration for device %s", device["_id"])
            probe_config["SnmpInfoDictionary"] = self._default_snmp_info_dict
            update_config = True

        if update_config is True:
            monitor_config = device["MonitorConfiguration"]
            for probe_index, probe in enumerate(monitor_config["Probes"]):
                if probe_index == probe_name:
                    monitor_config["Probes"][probe_index] = probe_config
                    break
            self._db.np.core.device.update(dict(_id=device["_id"]), {"$set": dict(MonitorConfiguration=monitor_config)})
            self._logger.warning("fixed snmp_info probe configuration for device %s", device["_id"])

        return probe_config


def get_probe_name():
    return "snmp_info"


def get_probe_description():
    return "SNMP Basic Information"


def get_probe_version():
    return "1.0.0"