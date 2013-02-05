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
    """Tests the ability the the Schedule manager to download a dummy schedule from the local disk.
    """
    
    # Attempt to initialize an instance of the schedule manager using a local file
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/application/core/tests/data/test_schedule', False)
    
    # Try to load the file
    update_deferred = schedule_manager.update_schedule()
    
    # Define an inline function to verify the schedule update results
    def check_schedule_update(update_results):
      self.assertEquals(update_results, True)
    
    update_deferred.addCallback(check_schedule_update)
    
    return update_deferred
  
  def test_local_file_load_invalid(self):
    """Tests that the ScheduleManager returns an error if an invalid schedule file is loaded.
    """
    
    # Attempt to initialize an instance of the schedule manager using a local file
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/application/core/tests/data/test_doesnt_exist', False)
    
    # Try to load the file
    update_deferred = schedule_manager.update_schedule()
    
    # Define an inline function to verify the schedule update results
    def check_schedule_update(update_results):
      self.assertEquals(update_results, False)
    
    update_deferred.addCallback(check_schedule_update)
    
    return update_deferred
