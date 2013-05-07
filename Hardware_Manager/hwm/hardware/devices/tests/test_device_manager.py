# Import required modules
import logging
from twisted.trial import unittest
from hwm.core.configuration import *
from hwm.hardware.devices import manager
from pkg_resources import Requirement, resource_filename

class TestDeviceManager(unittest.TestCase):
  """ This test suite tests the functionality of the device manager, which is responsible for initializing and providing
  access to device drivers.
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
    # Clear the configuration
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None
  
  def test_initialization_errors(self):
    """ This test verifies that device manager correctly generates the appropriate errors during the initialization 
    process.
    """
    
    # Attempt to initialize the device manager without loading any device configuration
    self.assertRaises(manager.InvalidDeviceConfig, manager.DeviceManager)
    
    # Load an empty device configuration and ensure the correct error is raised
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_empty.yml')
    self.assertRaises(manager.InvalidDeviceConfig, manager.DeviceManager)
    
    # Try to load a device configuration that contains a formatting error
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_invalid_format.yml')
    self.assertRaises(manager.InvalidDeviceConfig, manager.DeviceManager)
    
    # Load a device configuration that contains a non-existent driver
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_missing_driver.yml')
    self.assertRaises(manager.DriverNotFound, manager.DeviceManager)
    
    # Load a device configuration that contains duplicate entries
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_duplicate.yml')
    self.assertRaises(manager.InvalidDeviceConfig, manager.DeviceManager)
  
  def test_device_get(self):
    """ Tests that the device manager correctly returns a driver after being initialized with a valid device
    configuration.
    """
    
    # Initialize the device manager with a valid configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    device_manager = manager.DeviceManager()
    
    # Attempt to get an invalid device
    self.assertRaises(manager.DeviceNotFound, device_manager.get_device_driver, "not_real_yo")
    
    # Load a valid device and make sure everything is correct
    test_driver = device_manager.get_device_driver("test_device2")
    self.assertEqual(test_driver.device_name, "test_device2")
    self.assertEqual(test_driver.test_value(), "QWERTY")
  
  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}
