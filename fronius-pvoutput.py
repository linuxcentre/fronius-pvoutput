#!/bin/sh
# -*- mode: python; coding: utf-8 -*-
#
# Posts power and voltage data from Fronius single-phase inverters to pvoutput.org API
#
#    Copyright (C) 2015 Phil Lewis
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Phil Lewis
# License: GPLv3 (see LICENSE.txt)
#
#
""":"
for p in python26 python2.6 python27 python2.7 python; do
	[ -x /usr/bin/$p ] && P=/usr/bin/$p && exec $P -B "$0" "$@"
done
" """
import calendar
from datetime import datetime
import dateutil.parser
import json
from optparse import OptionParser
import os
import requests
import sys
import time


def getLastData( fileName = '/tmp/lastReading.json' ):
	try:
		with open( fileName ) as dataFile:
			data = json.load( dataFile )
	except IOError, e:
		# If no file exists then assume midnight today
		now = calendar.timegm( time.gmtime() )
		midnightTs = isoDateToSecs( datetime.fromtimestamp( now ).strftime( "%Y-%m-%dT00:00:00+00:00" ) )
		data = { 'dayEnergy':0, 'inverterVoltage':0, 'ts':midnightTs, }
	return data



def setLastData( data, fileName = '/tmp/lastReading.json' ):
	if opt.debug: print "DEBUG: Writing last data: %r -> %s" % ( data, fileName )
	if opt.dryRun: return
	with open( fileName, 'w') as dataFile:
		json.dump( data, dataFile )



def postBatchReadings( profileData, key, sid ):
	batchMax = 30
	batchReadings = []
	headers = {
		'X-Pvoutput-Apikey': key,
		'X-Pvoutput-SystemId': sid,
	}
	url = 'http://pvoutput.org/service/r2/addbatchstatus.jsp'

	# for each 300s profile Value:
	for data in profileData:
		readingTimeStamp = datetime.fromtimestamp( data['ts'] )
		dateYMD = readingTimeStamp.strftime( "%Y%m%d" )
		timeHM = readingTimeStamp.strftime( "%H:%M" )
		if opt.debug: print "BATCH ADD: dateYMD:", dateYMD, "timeHM:", timeHM, "Secs:", data['ts'], "inverterVoltage:", data['inverterVoltage'], "dayEnergy:", data['dayEnergy']
		batchReadings.append( "%s,%s,%f,,,,,%s" % ( dateYMD, timeHM, data['dayEnergy'], str( data['inverterVoltage'] ) ) )

	# REST API post
	i = 0
	while i < len( batchReadings ):
		# batch max
		thisBatch = batchReadings[ i:(i + batchMax) ]
		i += batchMax
		# batch:
		batchPayload = {
			'data':';'.join( thisBatch ), # batch readings
			#'c1':1, # cumulative
		}
		if opt.debug: print 'DEBUG: Data:', batchPayload

		if opt.dryRun:
			print "INFO: %r POST OK: 200" % ( url )
			continue

		# Send request
		r = requests.post( url, data = batchPayload, headers = headers )
		# Interpret responses
		if r.status_code >= 400:
			print "ERROR: %r %d bad request: '%s', data: %r" % ( url, r.status_code, r.text, batchPayload )
			return False
		else:
			if opt.debug:
				print "INFO: %r %d POST OK: '%s'" % ( url, r.status_code, r.text )
			else:
				print "INFO: %r %d POST OK" % ( url, r.status_code )
		time.sleep( 10 )

	return True



def postReading( dayEnergy, inverterVoltage, ts, key, sid ):
	readingTimeStamp = datetime.fromtimestamp( ts )
	dateYMD = readingTimeStamp.strftime( "%Y%m%d" )
	timeHM = readingTimeStamp.strftime( "%H:%M" )
	if opt.debug: print "POST: dateYMD:", dateYMD, "timeHM:", timeHM, "Secs:", ts, "inverterVoltage:", inverterVoltage, "dayEnergy:", dayEnergy

	url = 'http://pvoutput.org/service/r2/addstatus.jsp?key=%s&sid=%s&d=%s&t=%s&v1=%s&v6=%s' % (
		key, sid, dateYMD, timeHM, str( dayEnergy ), str( inverterVoltage )
	)

	if opt.dryRun:
		print "INFO: %r GET OK: 200" % ( url )
		return True

	r = requests.get( url )

	# Interpret responses
	if r.status_code >= 400:
		print "ERROR: %r %d bad GET request: '%s'" % ( url, r.status_code, r.text )
		return False
	else:
		if opt.debug:
			print "INFO: %r %d GET OK: '%s'" % ( url, r.status_code, r.text )
		else:
			print "INFO: %r %d GET OK" % ( url, r.status_code )
	return True



def secsToIsoDate( secs ):
	"""
	Return date/time from epoch secs in ISO8601 format 1997-07-16T19:20:30.45+01:00
	"""
	return datetime.fromtimestamp( secs ).strftime( '%Y-%m-%dT%H:%M:%S+00:00' )



def isoDateToSecs( isoDateString ):
	"""
	Converts an iso date string to seconds since 1970 - tz aware
	"""
	if isoDateString == '' or isoDateString == None:
		return 0
	# NOTE: not tz aware and %s not documented: dateutil.parser.parse( isoDateString ).strftime('%s')
	return calendar.timegm( dateutil.parser.parse( isoDateString ).utctimetuple() )



def getInverterReading( host ):
	# Send request
	url = 'http://' + host + '/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&DeviceID=1&DataCollection=CommonInverterData'
	print "INFO: Getting inverter reading"
	r = requests.get( url )
	# Interpret responses
	if r.status_code >= 400:
		print "ERROR: %s %d bad request: '%s'" % ( url, r.status_code, r.text )
		return None, None, None, None
	else:
		if opt.debug: print "INFO: %s %d OK: '%s'" % ( url, r.status_code, r.text )
	response = json.loads( r.text )

	timeStamp = response['Head']['Timestamp']
	instPower = response['Body']['Data']['PAC']['Value']
	dayEnergy = response['Body']['Data']['DAY_ENERGY']['Value']
	inverterVoltage = response['Body']['Data']['UAC']['Value']

	return instPower, dayEnergy, inverterVoltage, timeStamp



def getInverterArchiveReadings( host, last, endTs = None ):
	""" ENERGY
	http://<HOSTNAME>/solar_api/v1/GetArchiveData.cgi?Scope=System&StartDate=2015-10-20T00:00:00+01:00&EndDate=2015-10-21T00:00:00+01:00&Channel=EnergyReal_WAC_Sum_Produced
		"Body" : {
			"Data" : {
				"inverter\/1" : {
					"NodeType" : 97,
					"DeviceType" : 81,
					"Start" : "2015-10-20T00:00:00+01:00",
					"End" : "2015-10-20T23:59:59+01:00",
					"Data" : {
						"EnergyReal_WAC_Sum_Produced" : {
							"_comment" : "channelId=NNNNNNNN",
							"Unit" : "Wh",
							"Values" : {
								"0" : 0,
								"300" : 0,
								"600" : 0,
								"900" : 0,
								"1200" : 0,
	"""
	""" VOLTAGE
	http://<HOSTNAME>/solar_api/v1/GetArchiveData.cgi?Scope=System&StartDate=2015-10-20T00:00:00+01:00&EndDate=2015-10-21T00:00:00+01:00&Channel=Voltage_AC_Phase_1
	{
		"Head" : {
			"RequestArguments" : {
				"Scope" : "System",
				"StartDate" : "2015-10-20T00:00:00+01:00",
				"EndDate" : "2015-10-21T23:59:59+01:00",
				"Channel" : "Voltage_AC_Phase_1",
				"SeriesType" : "Detail",
				"HumanReadable" : "True"
			},
			"Status" : {
				"Code" : 0,
				"Reason" : "",
				"UserMessage" : "",
				"ErrorDetail" : {
					"Nodes" : []
				}
			},
			"Timestamp" : "2015-10-21T09:26:45+01:00"
		},
		"Body" : {
			"Data" : {
				"inverter\/1" : {
					"NodeType" : 97,
					"DeviceType" : 81,
					"Start" : "2015-10-20T00:00:00+01:00",
					"End" : "2015-10-20T23:59:59+01:00",
					"Data" : {
						"Voltage_AC_Phase_1" : {
							"_comment" : "channelId=NNNNN",
							"Unit" : "V",
							"Values" : {
								"28800" : 246,
								"29100" : 247.9,
								"29400" : 247.5,
								"29700" : 247.6,
								"30000" : 246.6,

	"""
	if endTs == None:
		endTs = calendar.timegm( time.gmtime() )
		## NOTE: Workaround bug in Inverter where EndDate is misinterpreted
		endDate = secsToIsoDate( endTs + 86400 )
	else:
		endDate = secsToIsoDate( endTs )
	ts = last['ts'] + 300
	dayEnergy = last['dayEnergy']
	startDate = secsToIsoDate( ts )
	profileDataByTs = {}

	# Energy Profile Reading Data
	url = 'http://' + host + '/solar_api/v1/GetArchiveData.cgi?Scope=System&StartDate=%s&EndDate=%s&Channel=EnergyReal_WAC_Sum_Produced' % ( startDate, endDate )
	# Send request
	print "INFO: Getting inverter energy archive readings"
	r = requests.get( url )
	# Interpret responses
	if r.status_code >= 400:
		print "ERROR: %s %d bad request: '%s'" % ( url, r.status_code, r.text )
		return None, None, None, None
	else:
		if opt.debug: print "INFO: %s %d OK: '%s'" % ( url, r.status_code, r.text )
	response = json.loads( r.text )

	# Derive profile data
	# Only works when Inverter is set to UTC - bugs in inverter REST API
	try:
		valueData = response['Body']['Data']['inverter/1']['Data']['EnergyReal_WAC_Sum_Produced']['Values']
	except KeyError:
		valueData = {}
	# Assumes oldest reading first
	keysIntList = []
	for k in valueData.keys():
		keysIntList.append( int( k ) )

	keys = sorted( keysIntList )
	for k in keys:
		offset = k
		profileEnergy = valueData[ str( k ) ]
		thisTs = ts + offset
		dayEnergy = dayEnergy + float( profileEnergy )
		profileDataByTs[ offset ] = { 'ts':thisTs, 'dayEnergy':dayEnergy, 'inverterVoltage':0 }


	# Voltage Profile Reading Data
	url = 'http://' + host + '/solar_api/v1/GetArchiveData.cgi?Scope=System&StartDate=%s&EndDate=%s&Channel=Voltage_AC_Phase_1' % ( startDate, endDate )
	# Send request
	print "INFO: Getting inverter voltage archive readings"
	r = requests.get( url )
	# Interpret responses
	if r.status_code >= 400:
		print "ERROR: %s %d bad request: '%s'" % ( url, r.status_code, r.text )
		return None, None, None, None
	else:
		if opt.debug: print "INFO: %s %d OK: '%s'" % ( url, r.status_code, r.text )
	response = json.loads( r.text )

	# Only works when Inverter is set to UTC - bugs in inverter REST API
	try:
		valueData = response['Body']['Data']['inverter/1']['Data']['Voltage_AC_Phase_1']['Values']
	except KeyError:
		valueData = {}
	# Assumes oldest reading first
	keysIntList = []
	for k in valueData.keys():
		keysIntList.append( int( k ) )
	keys = sorted( keysIntList )
	for k in keys:
		offset = k
		profileVoltage = valueData[ str( k ) ]
		thisTs = ts + offset
		if offset in profileDataByTs and 'inverterVoltage' in profileDataByTs[ offset ]:
			profileDataByTs[ offset ]['inverterVoltage'] = profileVoltage
		else:
			print "WARNING: ts %d is not an existing key in the list of profile energy values" % ( offset )

	# Sort result by ts
	profileData = []
	keysIntList = []
	for k in profileDataByTs.keys():
		keysIntList.append( k )
	keys = sorted( keysIntList )
	#print 'KEYS', keys, len( keys )
	for k in keys:
		# strip out zero reads
		if profileDataByTs[ k ]['inverterVoltage'] != 0:
			profileData.append( profileDataByTs[ k ] )
	return profileData


### MAIN ###
if __name__ == "__main__":

	parser = OptionParser()
	parser.add_option( "--host", dest = "host", default = None, help = "hostname/IP address of the inverter" )
	parser.add_option( "--repost", dest = "repost", default = None, help = "Re-post all data from this date (assuming it still exists int he inverter). Format: YYYY-MM-DD" )
	parser.add_option( "--key", "-k", dest = "key", default = None, help = "pvoutput.org API key" )
	parser.add_option( "--sid", "-s", dest = "sid", default = None, help = "pvoutput.org SID" )
	parser.add_option( "--dryrun", dest = "dryRun", action = "store_true", default = False, help = "dry-run no posting or writing to files" )
	parser.add_option( "--debug", dest = "debug", action = "store_true", default = False, help = "Debug output log level" )
	( opt, args ) = parser.parse_args()

	if opt.host == None:
		print "ERROR: Inverter address must be defined using --host"
		sys.exit( 1 )
	if opt.key == None or opt.sid == None:
		print "ERROR: pvoutput.org API key and sid options must be specified"
		sys.exit( 1 )

	# Normal mode
	if opt.repost == None:
		now = calendar.timegm( time.gmtime() )
		last = getLastData()
		if opt.debug: print "DEBUG: Last:", last

		# Midnight today
		midnightTs = isoDateToSecs( datetime.fromtimestamp( now ).strftime( "%Y-%m-%dT00:00:00+00:00" ) )
		# Ensure we start dailyTotal from zero if this is the next day
		if isoDateToSecs( datetime.fromtimestamp( last['ts'] ).strftime( "%Y-%m-%dT00:00:00+00:00" ) ) != midnightTs:
			if opt.debug: print "DEBUG: First reading of the day"
			last = { 'dayEnergy':0, 'inverterVoltage':0, 'ts':midnightTs, }
			if opt.debug: print "DEBUG: Last:", last

		# If last successful reading  > 300s ago:
		if opt.debug: print "DEBUG: Time diff:", ( now - last['ts'] )
		# get archive data between last reading time and now
		profileData = getInverterArchiveReadings( host = opt.host, last = last )
		"""
		# Single POST to pvoutput
		# for each 300s profile Value:
		for data in profileData:
			# POST to pvoutput
			if postReading( data['dayEnergy'], data['inverterVoltage'], data['ts'], key = opt.key, sid = opt.sid ):
				pass
		"""
		# Batch POST to pvoutput
		if postBatchReadings( profileData, key = opt.key, sid = opt.sid ):
			# Store last reading data: last energy value Wh + ISO8601 ts
			# Ensure we only store latest...
			if profileData != []:
				setLastData( data = profileData[-1] )

	# Day repost mode (YYYY-MM-DD)
	else:
		# Midnight of selected day
		midnightTs = isoDateToSecs( opt.repost + "T00:00:00+00:00" )
		endTs = midnightTs + 86400
		print "INFO: Reposting ", opt.repost
		last = { 'dayEnergy':0, 'inverterVoltage':0, 'ts':midnightTs, }
		if opt.debug: print "DEBUG: Last:", last

		# get archive data between last reading time and now
		profileData = getInverterArchiveReadings( host = opt.host, last = last, endTs = endTs )
		# POST to pvoutput
		postBatchReadings( profileData, key = opt.key, sid = opt.sid )


	"""
	# Don't use this anymore - use the archived values to gain sync with inverter 5-min periods
	instPower, dayEnergy, inverterVoltage, timeStamp = getInverterReading( opt.host )
	if instPower == None:
		sys.exit( 1 )
	ts = isoDateToSecs( timeStamp )
	print "Instantaneous power: %sW\nGenerated today: %sWh ts:%d" % ( instPower, dayEnergy, ts )


	if postReading( dayEnergy, inverterVoltage, ts, key = opt.key, sid = opt.sid ):
		# If successful, store last reading data: last energy value Wh + ISO8601 ts
	####	setLastData( data = { 'instPower':instPower, 'dayEnergy':dayEnergy, 'inverterVoltage':inverterVoltage, 'ts':ts, } )
		pass
	"""


	sys.exit( 0 )
