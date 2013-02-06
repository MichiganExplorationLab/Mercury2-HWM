# Import required modules
import unittest, logging
from ..configuration import *
from pkg_resources import Requirement, resource_filename

class TestConfiguration(unittest.TestCase):
  """
  This test case tests the functionality of the configuration module (and Config class).
  
  @note The configuration module creates a singleton instance of the Config class (accessed with Configuration).
  """
  
  def setUp(self):
    # Set a local reference to Configuration (how other modules should typically access Config)
    self.config = Configuration
    self.config.verbose_startup = False
    
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the configuration reference
    self.config = None
  
  def test_configuration_setup(self):
    # Verify that the version and data directory have been set
    valid_version = True
    if self.config.version is None or self.config.version == "":
      valid_version = False
    self.assertTrue(valid_version, "The HWM version was not specified in __init__.")
    
    # Verify that the data path has been set
    valid_data_directory = True
    if self.config.data_directory is None or self.config.data_directory == "":
      valid_data_directory = False
    self.assertTrue(valid_data_directory, "The local data directory location was not specified in __init__.")
  
  def test_user_option_standard_operation(self):
    # Attempt to add a dummy user option
    first_set_result = self.config.set('test_option', 'Test Value')
    self.assertTrue(first_set_result, "Could not set a user configuration option.")
    
    # Attempt to add a dummy option of a different type
    second_set_result = self.config.set('test_option_2', False)
    self.assertTrue(second_set_result, "Could not set a user configuration option.")
    
    # Attempt to read the recently set options
    first_read_result = self.config.get('test_option')
    self.assertEqual(first_read_result, 'Test Value', "The first read user option does not match what it was set to.")
    
    second_read_result = self.config.get('test_option_2')
    self.assertEqual(second_read_result, False, "The second read user option does not match what it was set to.")
    
    # Attempt to delete a user option
    first_delete_result = self.config.delete('test_option')
    self.assertTrue(first_delete_result, "There was an error deleting the first user option.")
    
    # Make sure the deleted option is gone
    self.assertRaises(OptionNotFound, self.config.get, 'test_option')
  
  def test_user_option_override(self):
    # Set the initial value
    self.config.set('override_test', 'Value A')
    
    # Override the initial value
    self.config.set('override_test', 'Value B')
    
    # Verify the value
    read_result = self.config.get('override_test')
    self.assertEqual(read_result, 'Value B')
  
  def test_user_option_read_nonexistent(self):
    # Attempt to read an non-existent value
    self.assertRaises(OptionNotFound, self.config.get, 'nonexistent_option')
  
  def test_user_option_delete_nonexistent(self):
    # Attempt to delete a non-existent value
    self.assertRaises(OptionNotFound, self.config.delete, 'nonexistent_option')
  
  def test_config_file_load(self):
    # Attempt to load a valid config file
    self.config.read_configuration(self.source_data_directory+'/application/core/tests/data/test_config.yml')
  
  def test_config_file_invalid_load(self):
    # Attempt to load an invalid config file
    self.assertRaises(Exception, self.config.read_configuration, self.source_data_directory+'/application/core/tests/data/test_config_invalid.yml')
  
  def test_default_option_set(self):
    # Load a valid configuration file
    self.config.read_configuration(self.source_data_directory+'/application/core/tests/data/test_config.yml')
    
    # Set the Mercury2 HWM defaults
    self.config._set_default_configuration()
    
    # Make sure one of those options can be read (shouldn't raise an exception)
    self.config.get('offline-mode')
  
  def test_default_option_override(self):
    # Load a valid configuration file
    self.config.read_configuration(self.source_data_directory+'/application/core/tests/data/test_config.yml')
    
    # Set the Mercury2 HWM defaults
    self.config._set_default_configuration()
    
    # Verify the option has the correct value (the one set in the file)
    read_result = self.config.get('schedule-update-timeout')
    self.assertEqual(read_result, 3, 'The configuration option value does not match what was set in the file.')
  
  def test_required_option_not_set(self):
    # Load a valid configuration file
    self.config.read_configuration(self.source_data_directory+'/application/core/tests/data/test_config.yml')
    
    # Validate required elements
    self.assertRaises(Exception, self.config._check_required_configuration)
  
  def test_protected_option_read(self):
    # Load the test configuration file
    self.config.read_configuration(self.source_data_directory+'/application/core/tests/data/test_config.yml')
    
    # Attempt to read one of the loaded options
    read_result = self.config.get('protected-option')
    self.assertEqual(read_result, 'Protected Value', 'The option value provided does not match the test configuration file\'s value.')
  
  def test_protected_option_set_protection(self):
    # Load the test configuration file
    self.config.read_configuration(self.source_data_directory+'/application/core/tests/data/test_config.yml')
    
    # Attempt to override a protected option
    self.assertRaises(OptionProtected, self.config.set, 'protected-option', 'Test Value')
  
  def test_protected_option_delete_protection(self):
    # Load the test configuration file
    self.config.read_configuration(self.source_data_directory+'/application/core/tests/data/test_config.yml')
    
    # Attempt to override a protected option
    self.assertRaises(OptionProtected, self.config.delete, 'protected-option')
  
