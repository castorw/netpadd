###Creating custom templates
You can easily create your own SNMP table templates by defining the structure as shown in the example above and attach 
it to device or to the template store collection. Just google the SNMP table structure you are interested in and create 
a JSON-like object as above. For example:

####Column-based table (manual-multi-level mode)
* Let's say we want to fetch the list of IP addresses assigned to device, we google for "snmp mib ip addresses"
* After a little research we can find the OIDs (eg. http://www.alvestrand.no/objectid/1.3.6.1.2.1.4.20.1.html)
* __1.3.6.1.2.1.4.20.1__ is the Base OID for us
* Then from the numbers 1, 2, 3, 4, 5 mentioned in "Subsidiary references (single level)" we create our table columns
* The resulting object (ready to be added to device's probe configuration) would look like:
```json
{
    "BaseOid" : "1.3.6.1.2.1.4.20.1",
    "ColumnNameMode" : "manual-multi-level",
    "Columns" : {
        "ipAdEntAddr" : 1,
        "ipAdEntIfIndex" : 2,
        "ipAdEntNetMask" : 3,
        "ipAdEntBcastAddr" : 4,
        "ipAdEntReasmMaxSize" : 5,
    }
}
```
* In case you wanted to add this table template to the templates collection __ns.snmp.tpl.table__, you need add the
 \_id attribute with the table name, so in this case it would be according
  to SNMP MIB specification __ipAddrTableEntry__ or __ipAddrTable__ _(depending on your preference)_

####Single-level list/table
It is possible to monitor entities which does not have a table structure, like ipRouteTableReduced table. For example,
you can monitor CPU usages which are only referenced as single OID values, which represent CPU usage. Example is CPU 
usage on MikroTik RouterOS devices, which has base OID __1.3.6.1.2.1.25.3.3.1.2__ and the following part of OID is 
the CPU core number (eg. __1.3.6.1.2.1.25.3.3.1.2.1__ for CPU0, __1.3.6.1.2.1.25.3.3.1.2.2__ for CPU1, etc...). 
Example configuration:
```json
{
    "BaseOid" : "1.3.6.1.2.1.25.3.3.1.2",
    "ColumnNameMode" : "auto-single-level",
    "SingleLevelTableStyle" : "list",
    "ColumnNamePrefix" : "cpu"
}
```

###Example SNMP table templates
SNMP table templates can be used in device configuration to make them fetch specific SNMP table-indexed data.
These templates can be saved in collection __ns.snmp.tpl.table__ and are intended for future integration.

* You can simply put any of these dictionaries(json objects) to snmp_info probe configuration on any device by adding
this section to __MonitorConfiguration.Probes.snmp_info.SnmpTableDictionary__ in collection __ns.core.device__ and 
possibly extending it to fit your needs. After you enter such dictionary in the device configuration document, the 
snmp_info probe will start collecting desired data from the device. __DO NOT INCLUDE THE \_id ATTRIBUTE.__
* These templates can be concentrated in collection __ns.snmp.tpl.table__, which is intended for future configuration-
related template integration.

```json
/* MikroTik RouterOS Wireless Registration Table (reduced) */
{
    "_id" : "rosWirelessReg",
    "ColumnNameMode" : "manual-multi-level",
    "BaseOid" : "1.3.6.1.4.1.14988.1.1.1.2.1",
    "Columns" : {
        "hardwareAddress" : 1,
        "snr" : 12,
        "uptime" : 11,
        "txRate" : 8,
        "rxRate" : 9,
        "txBytes" : 4,
        "rxBytes" : 5,
        "txPackets" : 6,
        "rxPackets" : 7
    }
}

/* SNMP Interface Table (reduced) */
{
    "_id" : "ifTableReduced",
    "ColumnNameMode" : "manual-multi-level",
    "BaseOid" : "1.3.6.1.2.1.2.2.1",
    "Columns" : {
        "ifSpeed" : 5,
        "ifType" : 3,
        "ifInOctets" : 10,
        "ifLastChange" : 9,
        "ifPhysAddress" : 6,
        "ifOutOctets" : 16,
        "ifAdminStatus" : 7,
        "ifDescr" : 2,
        "ifIndex" : 1,
        "ifMtu" : 4,
        "ifOperStatus" : 8
    }
}

/* SNMP IP Route List (reduced) */
{
    "_id" : "ipRouteTableReduced",
    "ColumnNameMode" : "manual-multi-level",
    "BaseOid" : "1.3.6.1.2.1.4.21.1",
    "Columns" : {
        "ipRouteDest" : 1,
        "ipRouteIfIndex" : 2,
        "ipRouteNextHop" : 7,
        "ipRouteType" : 8,
        "ipRouteProto" : 9,
        "ipRouteAge" : 10,
        "ipRouteMask" : 11,
        "ipRouteInfo" : 13
    }
}
```
