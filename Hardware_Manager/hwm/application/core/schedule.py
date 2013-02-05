""" @package hwm.application.core.schedule
Stores and maintains the reservation access schedule.

This module contains a class that is used to fetch, maintain, and provide access to the reservation schedule.
"""

# Import required modules
from configuration import Configuration
from twisted.internet import threads
import logging, json, threading

class ScheduleManager:
  """Represents a reservation access schedule.
  
  This class provides access to a copy of the reservation schedule. That hardware manager can use ScheduleManager to:
  * Download new copies of the reservation schedule from the user interface
  * Query for specific reservations
  * Access newly active reservations
  """
  
  def __init__(self, schedule_endpoint, load_from_network = True):
    """Initializes the schedule instance.
    
    @param schedule_endpoint  Where to load the reservation schedule from. This can either be a local file or a network 
                              address (such as the mercury2 user interface API).
    @param load_from_network  If set to true or left unspecified the schedule referenced by schedule_endpoint will be 
                              loaded over the network (instead of locally).
    """
    
    # Set the local configuration object reference
    self.config = Configuration
    
    # Create the schedule lock
    self.schedule_lock = threading.Lock()
    
    # Set the schedule parameters
    self.use_network_schedule = load_from_network
    self.schedule_location = schedule_endpoint
    self.schedule = {}
  
  def update_schedule(self):
    """Downloads the most recent version of the schedule from the active source.
    
    @note This method loads the schedule from the active source (either a local file or network address) and updates 
          the local copy. If use_local_schedule is true, the schedule will be loaded from a local file (specified in 
          the configuration files). If it is false, it will be loaded from the user interface API.
    
    @return Returns a deferred that will be called with the result of the file access (True or False).
    """
    
    # Setup local variables
    defer_download = None
    
    # Attempt to download the schedule
    if self.use_network_schedule:
      print 'test'
      #_download_remote_schedule()
    else:
      defer_download = threads.deferToThread(self._download_local_schedule)
    
    return defer_download
  
  def _download_local_schedule(self):
    """Downloads the set schedule from the local disk.
    
    This method downloads the local schedule from the disk and stores it in the schedule instance.
    
    @note The schedule file is passed to the constructor and specified by self.schedule_location.
    @note This method is intended to be called with threads.deferToThread.
    
    @return Returns True if the file is successfully loaded into the class and false otherwise.
    """
    
    # Setup local variables
    schedule_file = None
    
    # Attempt to open the schedule file
    try:
      schedule_file = open(self.schedule_location, 'r')
    except IOError:
      # Error loading the schedule file
      logging.error("There was an error loading the local schedule: "+self.schedule_location)
      return False
    
    # Parse the schedule JSON
    try:
      # Acquire a lock on the schedule to keep
      self.schedule_lock.acquire(True)
      try:
        self.schedule = json.load(schedule_file)
      finally:
        self.schedule_lock.release()
    except ValueError:
      # Error parsing the schedule JSON
      logging.error("Schedule manager could not parse schedule file: "+self.schedule_location)
      return False
    
    return True
