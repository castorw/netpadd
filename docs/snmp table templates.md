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
    },
    "BaseOid" : "1.3.6.1.4.1.14988.1.1.1.2.1",
    "_id" : "rosWirelessReg"
}

/* SNMP Interface Table (reduced) */
{
    "_id" : "ifTableReduced",
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
    },
    "BaseOid" : "1.3.6.1.2.1.2.2.1"
}

/* SNMP IP Route List (reduced) */
{
    "_id" : "ipRouteTableReduced",
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

###Creating custom templates
You can easily create your own SNMP table templates by defining the structure as shown in the example above and attach 
it to device or to the template store collection. Just google the SNMP table structure you are interested in and create 
a JSON-like object as above. For example:
* Let's say we want to fetch the list of IP addresses assigned to device, we google for "snmp mib ip addresses"
* After a little research we can find the OIDs (eg. http://www.alvestrand.no/objectid/1.3.6.1.2.1.4.20.1.html)
* __1.3.6.1.2.1.4.20.1__ is the Base OID for us
* Then from the numbers 1, 2, 3, 4, 5 mentioned in "Subsidiary references (single level)" we create our table columns
* The resulting object (ready to be added to device's probe configuration) would look like:
```json
{
    "BaseOid" : "1.3.6.1.2.1.4.20.1",
    "Columns" : {
        "ipAdEntAddr" : 1,
        "ipAdEntIfIndex" : 2,
        "ipAdEntNetMask" : 3,
        "ipAdEntBcastAddr" : 4,
        "ipAdEntReasmMaxSize" : 5,
    }
}
```