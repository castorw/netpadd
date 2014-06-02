import json
from pysnmp.entity.rfc3413.oneliner import cmdgen
import time
from ctrdn.netpadd.monitor import DeviceProbe

__author__ = 'Lubomir Kaplan <castor@castor.sk>'


class Probe(DeviceProbe):
    _default_snmp_port = None
    _default_snmp_community = None
    _default_snmp_version = None
    _default_snmp_info_dict = None
    _default_snmp_table_dict = None

    def __init__(self, config, db):
        DeviceProbe.__init__(self, config, db, "probe-snmp-info")

        assert self._config.get("probe_snmp_info", "default-snmp-port"), "no default snmp port configured"
        assert self._config.get("probe_snmp_info", "default-snmp-community"), "no default snmp community configured"
        assert self._config.get("probe_snmp_info", "default-snmp-version"), "no default snmp version configured"
        assert self._config.get("probe_snmp_info", "default-snmp-info-dictionary"), "no default snmp info dictionary \
        configured"
        assert self._config.get("probe_snmp_info", "default-snmp-table-dictionary"), "no default snmp table dictionary \
        configured"

        self._default_snmp_port = self._config.getint("probe_snmp_info", "default-snmp-port")
        self._default_snmp_community = self._config.get("probe_snmp_info", "default-snmp-community")
        self._default_snmp_version = self._config.get("probe_snmp_info", "default-snmp-version")
        self._default_snmp_info_dict = json.loads(self._config.get("probe_snmp_info", "default-snmp-info-dictionary"))
        self._default_snmp_table_dict = json.loads(self._config.get("probe_snmp_info", "default-snmp-table-dictionary"))

    def poll_device(self, device, probe_name, probe_config):
        probe_successful = False
        tables_probe_successful = False
        info_result = None
        tables_result = None
        probe_address_index = 0
        if len(device["IpAddress"]) < 1:
            return dict(Status=0, Error=dict(Id="NO_IP_ADDRESSES",
                                             Message="no internet protocol addresses defined for device"))

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

            # attempt to fetch info
            info_result = self._probe_info(probe_config, address_record)
            probe_successful = True if info_result["Status"] == 1 else False
            if probe_successful is False:
                snmp_error = info_result["Error"]
                self._logger.warn("info snmp error: %s", snmp_error)

            # attempt to fetch tables
            if probe_successful is True:
                tables_result = self._probe_tables(probe_config, address_record)
                tables_probe_successful = True if tables_result["Status"] == 1 else False
                if tables_probe_successful is False:
                    snmp_error = tables_result["Error"]
                    self._logger.warn("tables snmp error: %s", snmp_error)

            probe_address_index += 1
        end_time = time.time()

        result_dict = {}
        if probe_successful is False:
            result_dict["Status"] = 0
            result_dict["Error"] = dict(Id="SNMP_ERROR", Message=str(snmp_error))
            self._logger.warn("failed to get snmp info, device=%s, time=%f", device["_id"], (end_time-start_time))
        else:
            result_dict["Status"] = 1
            result_dict["SnmpInfoData"] = info_result["Data"]
            self._logger.debug("processed snmp info, device=%s, count=%d, time=%f",
                               device["_id"], len(info_result["Data"]), (end_time-start_time))
            if tables_probe_successful is True:
                result_dict["SnmpTableData"] = tables_result["Data"]
                self._logger.debug("processed snmp tables, device=%s, count=%d, time=%f",
                                   device["_id"], len(tables_result["Data"]), (end_time-start_time))
            else:
                self._logger.warning("failed to get snmp tables data for device=%s", device["_id"])
        return result_dict

    def _probe_tables(self, probe_config, address_record):
        table_result = {}
        for table_name, table_config in probe_config["SnmpTableDictionary"].iteritems():
            table = self._probe_single_table(table_config, probe_config, address_record)
            if table["Status"] == 0:
                return dict(Status=0, Error=table_result[table_name]["Error"])
            else:
                table_result[table_name] = table["Data"]
        return dict(Status=1, Data=table_result)

    def _probe_single_table(self, table_config, probe_config, address_record):
        cmd_generator = cmdgen.CommandGenerator()
        base_oid = table_config["BaseOid"]
        table_data = []
        snmpid_table_map = {}
        oid_column_map = {}
        lowest_oid = None
        highest_oid = None
        for col_name, col_oid in table_config["Columns"].iteritems():
            if lowest_oid is None or lowest_oid > col_oid:
                lowest_oid = col_oid
            if highest_oid is None or highest_oid < col_oid:
                highest_oid = col_oid
            oid_column_map[col_oid] = col_name
        last_oid = base_oid + "." + str(lowest_oid)

        probe_done = False

        snmp_error = None
        while not probe_done:
            last_oid = last_oid.encode('ascii', 'ignore')
            snmp_err_indication, snmp_err_status, snmp_err_index, snmp_var_binds = cmd_generator.bulkCmd(
                cmdgen.CommunityData(probe_config["SnmpCommunity"]),
                cmdgen.UdpTransportTarget((address_record["Address"], probe_config["SnmpPort"])),
                0, 10,
                last_oid)

            if snmp_err_indication:
                snmp_error = str(snmp_err_indication)
                break
            else:
                if snmp_err_status:
                    snmp_error = 'snmp error: %s at %s' % (snmp_err_status.prettyPrint(),
                                 snmp_err_index and snmp_var_binds[-1][int(snmp_err_index) - 1] or '?')
                    break
                else:
                    for oid_tuple in snmp_var_binds:
                        oid = oid_tuple[0][0]
                        oid_string = str(oid.prettyOut(oid))
                        value = oid_tuple[0][1]
                        value = value.prettyOut(value)
                        if not oid_string.startswith(base_oid):
                            probe_done = True
                            break
                        last_oid = oid_string
                        """:type : str"""
                        column_id = int(oid_string[len(base_oid)+1:oid_string.find(".", len(base_oid)+1)])
                        item_id = oid_string[oid_string.find(".", len(base_oid)+1)+1:]
                        if not column_id in oid_column_map:
                            break
                        if not item_id in snmpid_table_map:
                            table_data.append({oid_column_map[column_id]: value})
                            snmpid_table_map[item_id] = len(table_data)-1
                        else:
                            table_data[snmpid_table_map[item_id]][oid_column_map[column_id]] = value

            if not snmp_error is None:
                self._logger.error("snmp tables error: %s", snmp_error)
                break

        if not snmp_error is None:
            return dict(Status=0, Error=snmp_error)
        else:
            return dict(Status=1, Data=table_data)

    @staticmethod
    def _probe_info(probe_config, address_record):
        cmd_generator = cmdgen.CommandGenerator()
        snmp_error = None
        snmp_data = None

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
        if not snmp_error is None:
            return dict(Status=0, Error=snmp_error)

        return dict(Status=1, Data=snmp_data)

    def validate_configuration(self, device, probe_config):
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
        if not "SnmpTableDictionary" in probe_config:
            self._logger.warn("no SnmpTableDictionary in probe configuration for device %s", device["_id"])
            probe_config["SnmpTableDictionary"] = self._default_snmp_table_dict
            update_config = True

        if update_config is True:
            self._logger.warning("fixed snmp_info probe configuration for device %s", device["_id"])
            return probe_config

        return None


def get_probe_name():
    return "snmp_info"


def get_probe_description():
    return "SNMP Information Fetcher"


def get_probe_version():
    return "1.0.0"