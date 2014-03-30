#!/usr/bin/python

"""
This script is used to generate schedules for the Mercury2 hardware manager. 

It uses the fetchTLE API to load the pass schedule for the specified satellite and ground station and generates a 
schedule file for those passes. This script will eventually be replaced by the Mercury2 user interface, which will be 
much more user-friendly.
"""

# Required packages
import json
import urllib2
import sys
import time

# Configuration
schedule_file = "/home/mxl/Desktop/Mercury2 Testing/FXB_Configuration/Configuration/var/local/Mercury2-HWM/schedules/offline_schedule.json"
satellite = "MCUBED-2"
ground_station = "MXL"
pipeline = "ICOM_Pipeline"
min_elevation = 1
pass_count = 20

print "Mercury2 HWM Schedule Generation Script\n"

# Load the satellite's most recent TLE
print "- Loading "+satellite+"'s most recent TLE from fetchTLE."
tle_api = "http://exploration.engin.umich.edu/satops/fetchtle/api/satellites/"+satellite+".json"
try:
  tle_json = urllib2.urlopen(tle_api)
except urllib2.URLError as e:
  print "[Error] Could not load TLE: "+str(e) 
  sys.exit(1)

try:
  api_results = json.load(tle_json)
except ValueError:
  print "[Error] Could not parse TLE JSON from fetchTLE."
  sys.exit(1)

if api_results['status']['status'] == "error":
  print "[Error] An error occured fetching the satellite's TLE: "+api_results['status']['message']
  sys.exit(1)

tle_line_1 = api_results['satellites'][satellite]['tle']['raw_l1']
tle_line_2 = api_results['satellites'][satellite]['tle']['raw_l2']

# Load the satellite's passes
print "- Loading "+satellite+"'s upcoming passes over the "+ground_station+" ground station from fetchTLE."
passes_api = "http://exploration.engin.umich.edu/satops/fetchtle/api/passes/"+satellite+".json?timestamp="+str(int(time.time())-60*60*24)+"&pass_count="+str(pass_count)+"&ground_stations=MXL&min_elevations="+str(min_elevation)+"&show_all_passes=false"
try:
  passes_json = urllib2.urlopen(passes_api)
except urllib2.URLError as e:
  print "[Error] Could not load passes: "+str(e) 
  sys.exit(1)

passes = {"generated_at":int(time.time()), "reservations": []}
try:
  api_results = json.load(passes_json)
except ValueError:
  print "[Error] Could not parse pass JSON from fetchTLE."
  sys.exit(1)

if api_results['status']['status'] == "error":
  print "[Error] An error occured fetching the passes: "+api_results['status']['message']
  sys.exit(1)

# Generate the HWM schedule JSON
for temp_pass in api_results['passes']:
  temp_pass = temp_pass['pass']

  temp_reservation = {}
  temp_reservation['reservation_id'] = str(temp_pass['orbit_number'])
  temp_reservation['user_id'] = "1"
  temp_reservation['username'] = "devuser"
  temp_reservation['time_start'] = temp_pass['aos'] - 60*2 # Give the antenna controller an extra 2 minutes to align before AOS
  temp_reservation['time_end'] = temp_pass['los']
  temp_reservation['description'] = satellite+" pass on "+time.strftime("%D %H:%M", time.localtime(temp_pass['aos']))
  temp_reservation['pipeline_id'] = pipeline
  temp_reservation['active_services'] = {"tracker": "sgp4_propagation_service"}
  
  temp_reservation['setup_commands'] = []
  set_tle_command = {
    "command": "set_target_tle",
    "destination": pipeline+".SGP4_tracker",
    "parameters": {
      "line_1": tle_line_1,
      "line_2": tle_line_2
    }
  }
  temp_reservation['setup_commands'].append(set_tle_command)

  passes['reservations'].append(temp_reservation)

# Save the schedule
print "- Writing JSON to schedule file."
schedule_json = json.dumps(passes)
schedule_file = open(schedule_file, 'w')
schedule_file.write(schedule_json)

