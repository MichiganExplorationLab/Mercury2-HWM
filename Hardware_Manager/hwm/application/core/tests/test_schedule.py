# Import required modules
from twisted.trial import unittest
from hwm.application.core import schedule
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
    """Tests the ability the the Schedule manager to download a valid dummy schedule from the local disk and update its 
    local schedule copy.
    """
    
    # Attempt to initialize an instance of the schedule manager using a local file
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/application/core/tests/data/test_schedule_valid.json')
    
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
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/application/core/tests/data/test_schedule_invalid.json')
    
    # Try to load the file
    update_deferred = schedule_manager.update_schedule()
    
    return self.assertFailure(update_deferred, schedule.ScheduleError)
  
  def test_local_file_load_missing(self):
    """Tests that the ScheduleManager returns an error if a missing schedule file is requested.
    """
    
    # Attempt to initialize an instance of the schedule manager using a local file
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/application/core/tests/data/test_doesnt_exist.json')
    
    # Try to load the file
    update_deferred = schedule_manager.update_schedule()
    
    return self.assertFailure(update_deferred, schedule.ScheduleError)
