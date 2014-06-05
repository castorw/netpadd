netpadd
=======
Simple network monitor based on python and mongodb

#Significant updates

#Description
The netpadd (_netpad daemon_) is a simple network monitoring framework (_currently in need of lots of development_), 
programmed in __python__ and using __MongoDB__ document storage as database unit for storing received and analyzed data.

###Currently built-in probes
* __ping__ (_probe_ping.py_) is a simple ICMP ping probe, which tests the remote devices by issuing ICMP ping requests 
and waits for responses from remote device. It's configuration is automatically generated before first probe to device 
in __Probes__ section of __MonitorConfiguration__ section of device configuration document. Example configuration:
```json
{
            "ping" : {
                "PingTimeout" : 2,
                "PingAddress" : "all",
                "PingCount" : 4
            }
}
```
The example above pings every address of the desired device 4 times every polling and waits maximally 2 seconds for 
reply from device. This configuration is automatically generated for device without module configuration present at 
polling time. This default configuration can be modified in the _netpadd.conf_ configuration file.

* __snmp_info__ (_probe_snmp_info.py_) is a simple SNMP data fetcher which can fetch single values and tables using 
SNMP protocol from device. It's configuration is pretty straightforward and allows you to customize it per-device. 
Example configuration from __Probes__ section of __MonitorConfiguration__ section from device configuration document:
```json
{
            "snmp_info" : {
                "SnmpPort" : 161,
                "SnmpCommunity" : "netpad",
                "SnmpTableDictionary" : {
                    "ifTable" : {
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
                },
                "SnmpInfoDictionary" : {
                    "sysDescr" : "1.3.6.1.2.1.1.1.0",
                    "sysName" : "1.3.6.1.2.1.1.5.0",
                    "sysLocation" : "1.3.6.1.2.1.1.6.0",
                    "sysUptime" : "1.3.6.1.2.1.1.3.0",
                    "sysContact" : "1.3.6.1.2.1.1.4.0"
                },
                "SnmpVersion" : "2c"
            }
}
```
The example above uses SNMP version 2c with community _netpad_ to acquire information mentioned in configuration from 
device. The __SnmpInfoDictionary__ section is used to specify specific values to receive from remote device. The 
__SnmpTableDictionary__ describes tables to be acquired from remote device. This example above requests interface table 
from device with some of the basic information. This configuration is automatically added to every device's 
configuration before first polling. The default template can be modified in _netpadd.conf_ configuration file.

###Required modules
Netpad daemon requires the following external python modules:
* pymongo
* pysnmp

###Configuring netpadd
In order to configure netpadd you need to do the following:
* create a copy (or rename) file __netpadd.conf.example__ to __netpadd.conf__ and set attributes so it fits your 
configuration

###Adding devices to monitor
You need to manually create device entries for now (no gui or cli available),
insert device records as follows in example show below to collection __np.core.device__:
```json
{
    "Description" : "Example Gateway",
    "Hostname" : "gateway.example.com",
    "IpAddress" : [ 
        {
            "Version" : 4,
            "Address" : "10.0.0.1"
        }, 
        {
            "Version" : 6,
            "Address" : "::1"
        }
    ],
    "MonitorEnabled" : true
}
```
* Make sure parameter _MonitorEnabled_ is set to _true_, if you want the device to be monitored
* The netpad daemon will automatically add required configuration to you device document

###Launching netpadd
You can start netpadd by launching:
```shell
    ./netpadd
```
without any arguments - all configuration should be in _netpadd.conf_
