# Import required modules
from twisted.trial import unittest
from hwm.sessions import schedule
from pkg_resources import Requirement, resource_filename
import logging

class TestSchedule(unittest.TestCase):
  """
  This test suite tests the functionality of the schedule manager (ScheduleManager).
  """
  
  def setUp(self):
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def test_local_file_load(self):
    """Tests the ability of the Schedule manager to download a valid dummy schedule from the local disk and update its 
    local schedule copy.
    """
    
    # Attempt to initialize an instance of the schedule manager using a local file
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    
    # Try to load the file
    update_deferred = schedule_manager.update_schedule()
    
    # Define an inline function to verify the schedule update results
    def check_schedule_update(update_results):
      self.assertNotEquals(update_results, False)
    
    update_deferred.addCallback(check_schedule_update)
    
    return update_deferred
  
  def test_local_file_load_invalid(self):
    """Verifies that ScheduleManager rejects schedules that don't fit the schedule schema requirements (see included 
    documentation for requirements).
    """
    
    # Attempt to initialize an instance of the schedule manager using a local file
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_invalid.json')
    
    # Try to load the file
    update_deferred = schedule_manager.update_schedule()
    
    return self.assertFailure(update_deferred, schedule.ScheduleError)
  
  def test_local_file_load_missing(self):
    """Tests that the ScheduleManager returns an error if a missing schedule file is requested.
    """
    
    # Attempt to initialize an instance of the schedule manager using a local file
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_doesnt_exist.json')
    
    # Try to load the file
    update_deferred = schedule_manager.update_schedule()
    
    return self.assertFailure(update_deferred, schedule.ScheduleError)
  
  def test_remote_file_load_missing(self):
    """Tests the schedule manager's ability to respond to an invalid schedule URL.
    """
    
    # Attempt to initialize an instance of the schedule manager using a local file
    schedule_manager = schedule.ScheduleManager('http://invalid-url.invalid')
    
    # Try to load the file
    update_deferred = schedule_manager.update_schedule()
    
    return self.assertFailure(update_deferred, schedule.ScheduleError)
  
  def test_get_active_reservations(self):
    """Tests that the schedule manager returns the reservations that are active (i.e. time_start < current time < time_end), while
    ignoring the inactive ones.
    
    @note The end time of one of the reservations in the test schedule is set to 2019 to make this test pass.
    """
    
    # Initialize an instance of the schedule manager using a local file
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    
    # Load the file
    update_deferred = schedule_manager.update_schedule()
    
    # Define an inline function to verify the active reservation return feature
    def check_schedule_update(update_results):
      # Attempt to get the active reservations
      active_reservations = schedule_manager.get_active_reservations()
      
      # Verify the correct number of active reservations was returned
      self.assertEqual(len(active_reservations), 3, "Too many active reservations were returned based on the test JSON file.")
    
    update_deferred.addCallback(check_schedule_update)
    
    return update_deferred
