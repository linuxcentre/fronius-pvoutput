# fronius-pvoutput
Tool for uploading Energy and Voltage data from Fronius Inverters to pvoutput.org

## Requirements
* Linux (will probably work on any unix)
* python 2.6+ (not tested on python 3.*)
* Fronius single-phase Inverter (tested on a Primo 3.0-1 and Galvo 2.0-1)

## NOTES
* Ensure your inverter is in UTC timezone because as of the time of writing the Fronius firmware for the REST API is quite buggy.
* Never modifies anything in the inverter.
* The first time you run it will only post data from today.

## Installation
* Download
* Add to crond (e.g. '/etc/crontab') and run every 5 minutes. e.g:
```
# Run every 5 minutes between 4am and 10pm
*/5 4-21 * * * root /path/to/fronius-pvoutput.py --sid <SID> --key <API KEY> --host <Inverter address> --debug >> /var/log/fronius-pvoutput.log
```
* View the log file
```
tail -f /var/log/fronius-pvoutput.log
```

## Re-POSTing historical data
If you want to post data from previous days just use the --repost YYYY-MM-DD option.

## Testing
Use the --dryrun and --debug options
