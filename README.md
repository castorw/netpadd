netpadd
=======
Simple network monitor based on python and mongodb

###Required modules
Netpad daemon requires the following external python modules:
* pymongo
* pysnmp

###Configuring netpadd
In order to configure netpadd you need to do the following:
* create a copy (or rename) file __netpadd.conf.example__ to __netpadd.conf__ and set attributes so it fit your confiuration

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
