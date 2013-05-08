""" @package hwm.sessions.schedule
Stores and maintains the reservation access schedule.

This module contains a class that is used to fetch, maintain, and provide access to the reservation schedule.
"""

# Import required modules
import logging, json, jsonschema, threading, urllib2, time
from hwm.core.configuration import Configuration
from twisted.internet import threads

class ScheduleManager:
  """Represents a reservation access schedule.
  
  This class provides access to a copy of the reservation schedule. That hardware manager can use ScheduleManager to:
  * Download new copies of the reservation schedule from the user interface
  * Query for specific reservations
  * Access newly active reservations
  """
  
  def __init__(self, schedule_endpoint):
    """Initializes the schedule instance.
    
    @param schedule_endpoint  Where to load the reservation schedule from. This can either be a local file or a network 
                              address (such as the mercury2 user interface API). If it begins with 'http', it will be 
                              treated as a network address.
    """
    
    # Set the local configuration object reference
    self.config = Configuration
    
    # Check if the schedule will be loaded from the network
    self.use_network_schedule = schedule_endpoint.startswith('http')
    
    # Set the schedule parameters
    self.schedule_location = schedule_endpoint
    self.schedule = {}
    self.last_updated = 0
  
  def update_schedule(self):
    """Downloads the most recent version of the schedule from the active source.
    
    @note This method loads the schedule from the active source (either a local file or network address) and updates 
          the local copy using callbacks. If use_local_schedule is true, the schedule will be loaded from a local file 
          (specified in the configuration files). If it is false, it will be loaded from the user interface API.
    
    @return Returns a deferred that will be called with the result of the file access (the schedule object or a Failure).
    """
    
    # Setup local variables
    defer_download = None
    
    # Attempt to download the schedule
    if self.use_network_schedule:
      defer_download = threads.deferToThread(self._download_remote_schedule)
    else:
      defer_download = threads.deferToThread(self._download_local_schedule)
    
    # Add a callback to store the schedule
    defer_download.addCallback(self._validate_schedule)
    defer_download.addCallback(self._save_schedule)
    
    return defer_download
  
  def get_active_reservations(self):
    """Returns a list of the currently active reservations (by timestamp).
    
    @note This method will return all active reservations whether or not the session coordinator is all ready responding
          to them. It is the responsibility of the coordinator to handle duplicates.
    
    @return Returns a list of the reservations that are currently active. If no reservations are active, an empty list
            will be returned.
    """
    
    # Setup local variables
    temp_active_reservations = []
    current_time = time.time()
    
    # Loop through the schedule and find active reservations
    if len(self.schedule) > 0:
      for reservation_id in self.schedule:
        # Test the reservation
        temp_reservation = self.schedule[reservation_id]
        
        if temp_reservation['time_start'] < current_time and temp_reservation['time_end'] > current_time:
          temp_active_reservations.append(temp_reservation)
    
    return temp_active_reservations
  
  def _validate_schedule(self, schedule_load_result):
    """Validates the newly loaded schedule JSON.
    
    This callback validates the format of the new schedule against the JSON schedule schema.
    
    @throw Throws ScheduleError if the schedule represented by schedule_load_result isn't valid.
    
    @param schedule_load_result  The result of the attempted schedule download.
    @retun Returns a python object representing the new schedule.
    """
    
    # Define the schema that determines what a valid schedule looks like
    schedule_schema = {
      "type": "object",
      "$schema": "http://json-schema.org/draft-03/schema",
      "required": True,
      "properties": {
        "generated_at": {
          "type": "number",
          "id": "generated_at",
          "required": True
        },
        "reservations": {
          "type": "array",
          "id": "reservations",
          "required": True,
          "items": {
            "type": "object",
            "additionalProperties": True, # Allows extra properties to be added to each reservation object
            "properties": {
              "hardware_settings": {
                "type": "object",
                "id": "hardware_settings",
                "required": True,
                "additionalProperties": {
                  # Device settings defined with these additional properties
                  "type": "object",
                  "additionalProperties": True, # Allows extra device properties to be set
                  "properties": {
                    "device_id": {
                      "type": "string",
                      "required": True
                    }
                  }
                }
              },
              "pipeline_id": {
                "type": "string",
                "id": "pipeline_id",
                "required": True
              },
              "time_end": {
                "type": "number",
                "id": "time_end",
                "required": True
              },
              "time_start": {
                "type": "number",
                "id": "time_start",
                "required": True
              },
              "reservation_id": {
                "type": "string",
                "id": "reservation_id",
                "required": True
              },
              "user_id": {
                "type": "string",
                "id": "user_id",
                "required": True
              }
            }
          }
        }
      }
    }
    
    # Validate the JSON schema
    schema_validator = jsonschema.Draft3Validator(schedule_schema)
    try:
      schema_validator.validate(schedule_load_result)
    except jsonschema.ValidationError:
      # Invalid schedule JSON
      logging.error("Provided schedule did not meet JSON schema requirements: "+self.schedule_location)
      raise ScheduleError('Local schedule file did not contain a valid schedule (invalid schema).')
    
    return schedule_load_result
  
  def _save_schedule(self, schedule_load_result):
    """Saves the provided schedule to the ScheduleManager class instance.
    
    @note This method is intended to be used as a callback for the deferred returned by the various schedule download 
          methods.
    
    @param schedule_load_result  The result of the attempted schedule download.
    @return Returns a python object representing the new schedule. Note this is represents the raw JSON objects before
            and filters or modifications have been applied.
    """
    
    # Set the update time
    self.last_updated = int(time.time())
    
    # Loop through the schedule and build the dictionary
    for schedule_reservation in schedule_load_result['reservations']:
      self.schedule[schedule_reservation['reservation_id']] = schedule_reservation
    
    # Update the local schedule copy and pass it along
    return schedule_load_result
  
  def _download_remote_schedule(self):
    """Loads the schedule from the schedule's URL.
    
    This method loads the the schedule from a URL (e.g. the mercury2 user interface) and returns it.
    
    @throw Throws ScheduleError if an error occurs while downloading or parsing the schedule.
    
    @note This method is intended to be called with threads.deferToThread. The returned schedule will be passed to the 
          resulting deferred's callback chain.
    
    @return Returns a python object representing the downloaded schedule.
    """
    
    # Setup local variables
    temp_schedule = None
    schedule_file = None
    
    # Attempt to download the JSON file
    try:
      schedule_request = urllib2.Request(self.schedule_location)
      schedule_opener = urllib2.build_opener()
      schedule_file = schedule_opener.open(schedule_request, None, self.config.get('schedule-update-timeout'))
    except:
      # Error downloading the file
      logging.error("There was an error downloading the schedule: "+self.schedule_location)
      raise ScheduleError('Could not download schedule from URL.')
    
    # Parse the schedule JSON
    try:
      temp_schedule = json.load(schedule_file)
    except ValueError:
      # Error parsing the schedule JSON
      logging.error("Schedule manager could not parse remote schedule file: "+self.schedule_location)
      raise ScheduleError('Could not parse remote schedule file (invalid JSON).')
    
    return temp_schedule
  
  def _download_local_schedule(self):
    """Loads the schedule from the local disk.
    
    This method loads the local schedule from the disk and returns it.
    
    @throw Throws ScheduleError if an error occurs while loading or parsing the schedule.
    
    @note The schedule file is passed to the constructor and specified by self.schedule_location.
    @note This method is intended to be called with threads.deferToThread. The returned schedule will be passed to the 
          resulting deferred's callback chain.
    
    @return Returns a python object representing the schedule if successful.
    """
    
    # Setup local variables
    schedule_file = None
    temp_schedule = None
    
    # Attempt to open the schedule file
    try:
      schedule_file = open(self.schedule_location, 'r')
    except IOError:
      # Error loading the schedule file
      logging.error("There was an error loading the local schedule: "+self.schedule_location)
      raise ScheduleError('Could not load schedule from disk.')
    
    # Parse the schedule JSON
    try:
      temp_schedule = json.load(schedule_file)
    except ValueError:
      # Error parsing the schedule JSON
      logging.error("Schedule manager could not parse schedule file: "+self.schedule_location)
      raise ScheduleError('Could not parse local schedule file (invalid JSON).')
    
    return temp_schedule

# Define schedule related exceptions
class ScheduleError(Exception):
  pass
