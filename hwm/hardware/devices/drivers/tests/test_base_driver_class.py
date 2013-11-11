# Import required modules
import logging
from twisted.trial import unittest
from mock import MagicMock
from hwm.core.configuration import *
from hwm.hardware.devices import manager
from hwm.hardware.devices.drivers import driver
from pkg_resources import Requirement, resource_filename

class TestBaseDriver(unittest.TestCase):
  """ This test suite tests the functionality of the base driver class that all other drivers inherit from.
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

  def test_loading_device_state(self):
    """ Tests that the Driver class get_state() method works as expected.
    """

    # Load a device to test with
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    device_manager = manager.DeviceManager()
    test_driver = device_manager.get_device_driver("test_device")

    # Try to load state
    self.assertRaises(driver.StateNotDefined, test_driver.get_state)

  def test_loading_command_handler(self):
    """ Tests that the Driver class returns its command handler (if it has one).
    """

    # Load a device to test with
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    device_manager = manager.DeviceManager()
    test_driver = device_manager.get_device_driver("test_device4")

    # Try to load the command handler for a device that doesn't have one
    self.assertRaises(driver.CommandHandlerNotDefined, test_driver.get_command_handler)

    # Give the device a mock command handler and try to load it
    test_command_handler = MagicMock()
    test_driver._command_handler = test_command_handler
    self.assertTrue(test_driver.get_command_handler() is test_command_handler)

  def test_writing_device_output(self):
    """ Tests that the Driver class can pass its output to its registered pipelines. The default implementation of the 
    Driver.write_output() method only writes to active pipelines that specify this device as its output device.
    """ 

    # Load a device to test with
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    device_manager = manager.DeviceManager()
    test_driver = device_manager.get_device_driver("test_device")

    # Create some mock pipelines and register them with the device
    test_pipeline = MagicMock()
    test_pipeline.id = "test_pipeline"
    test_pipeline.is_active = False
    test_driver.register_pipeline(test_pipeline)
    test_pipeline_2 = MagicMock()
    test_pipeline_2.id = "test_pipeline_2"
    test_pipeline_2.is_active = True
    test_driver.register_pipeline(test_pipeline_2)
    test_pipeline_3 = MagicMock()
    test_pipeline_3.id = "test_pipeline_3"
    test_pipeline_3.is_active = True
    test_pipeline_3.output_device = test_driver
    test_driver.register_pipeline(test_pipeline_3)

    # Write some output to the associated pipelines
    test_driver.write_output("waffles")

    # Make sure the output never made it to the non-active pipeline
    self.assertEqual(test_pipeline.write_output.call_count, 0)

    # Make sure that test_pipeline_2 was never called (doesn't specify test_device as its output device)
    self.assertEqual(test_pipeline_2.write_output.call_count, 0)

    # Verify that test_pipeline_3 was called with the correct output
    test_pipeline_3.write_output.assert_called_once_with("waffles")

  def test_writing_device_telemetry(self):
    """ Tests that the Driver class can pass device telemetry and extra data streams to its registered pipelines via the
    Driver.write_telemetry() method. This method should always be used to write extra device data and telemetry back to 
    its pipelines.
    """ 

    # Load a device to test with
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    device_manager = manager.DeviceManager()
    test_driver = device_manager.get_device_driver("test_device")

    # Create some mock pipelines and register them with the device
    test_pipeline = MagicMock()
    test_pipeline.id = "test_pipeline"
    test_pipeline.is_active = False
    test_pipeline.output_device = test_driver
    test_driver.register_pipeline(test_pipeline)
    test_pipeline_2 = MagicMock()
    test_pipeline_2.id = "test_pipeline_2"
    test_pipeline_2.is_active = True
    test_pipeline_2.output_device = test_driver
    test_driver.register_pipeline(test_pipeline_2)

    # Write a telemetry point to the driver
    test_driver.write_telemetry("test_stream", "waffles", binary=False, test_header=42)

    # Make sure the telemetry was never passed to test_pipeline (not active)
    self.assertEqual(test_pipeline.write_telemetry.call_count, 0)

    # Make sure that the telemetry point was correctly passed to the active pipeline (test_pipeline_2). We can't just
    # use assert_called_once_with() because the timestamp argument is generated after write_telemetry() is called.
    mock_call = test_pipeline_2.write_telemetry.call_args_list[0]
    test_args, test_kwords = mock_call
    self.assertEqual(test_args[0], "test_device")
    self.assertEqual(test_args[1], "test_stream")
    int(test_args[2]) # Check if the auto generated timestamp is an integer (will throw exception otherwise)
    self.assertEqual(test_args[3], "waffles")
    self.assertTrue("binary" in test_kwords and test_kwords["binary"] == False)
    self.assertTrue("test_header" in test_kwords and test_kwords["test_header"] == 42)
  
  def test_pipeline_registration(self):
    """ Verifies that the base driver class can correctly register pipelines
    """

    # Load a valid device configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    device_manager = manager.DeviceManager()

    # Load a driver to test with
    test_driver = device_manager.get_device_driver("test_device")

    # Create some mock pipelines to register with the device
    test_pipeline = MagicMock()
    test_pipeline.id = "test_pipeline"
    test_pipeline.output_device = test_driver
    test_pipeline_2 = MagicMock()
    test_pipeline_2.id = "test_pipeline_2"
    test_pipeline_2.output_device = test_driver

    # Register the pipelines
    test_driver.register_pipeline(test_pipeline)
    test_driver.register_pipeline(test_pipeline_2)
    self.assertTrue((test_driver.associated_pipelines[test_pipeline.id].id == test_pipeline.id) and
                    (test_driver.associated_pipelines[test_pipeline.id].output_device is test_driver))
    self.assertTrue((test_driver.associated_pipelines[test_pipeline_2.id].id == test_pipeline_2.id) and
                    (test_driver.associated_pipelines[test_pipeline_2.id].output_device is test_driver))

    # Make sure that pipelines can't be re-registered
    self.assertRaises(driver.PipelineAlreadyRegistered, test_driver.register_pipeline, test_pipeline)

  def test_driver_reservation(self):
    """ Tests the reservation functionality of the base driver class.
    """
    
    # Load a valid device configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    device_manager = manager.DeviceManager()
    
    # Get a driver to test
    test_driver = device_manager.get_device_driver("test_device2")
    
    # Reserve the driver
    test_driver.reserve_device()
    
    # Try to reserve it again
    self.assertRaises(driver.DeviceInUse, test_driver.reserve_device)

    # Verify that the driver is reserved and active
    self.assertTrue(test_driver.is_locked)
    self.assertTrue(test_driver.is_active)
    self.assertEqual(test_driver._use_count, 1)
    
    # Unlock the driver a few times and make sure it was freed correctly
    test_driver.free_device()
    self.assertTrue(not test_driver.is_locked)
    self.assertTrue(not test_driver.is_active)
    test_driver.free_device()
    self.assertTrue(not test_driver.is_locked)
    self.assertTrue(not test_driver.is_active)
    self.assertEqual(test_driver._use_count, 0)

    # Reserve the driver again
    test_driver.reserve_device()
  
  def test_concurrent_driver_reservation(self):
    """ Tests the reservation functionality of the base driver class when using a device configured for concurrent
    access.
    """

    # Load a valid device configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    device_manager = manager.DeviceManager()
    
    # Load a driver to test with
    test_driver = device_manager.get_device_driver("test_webcam")
    
    # Try to reserve the driver twice in a row (should be allowed because the device allows concurrent use)
    test_driver.reserve_device()
    test_driver.reserve_device()

    # Verify that the device was reserved correctly
    self.assertTrue(test_driver.is_active)
    self.assertTrue(not test_driver.is_locked)
    self.assertEqual(test_driver._use_count, 2)

    # Try un-reserving the driver a few times
    test_driver.free_device()
    self.assertTrue(test_driver.is_active)
    test_driver.free_device()
    self.assertTrue(not test_driver.is_active)
    self.assertTrue(not test_driver.is_locked)
    test_driver.free_device()
    self.assertTrue(not test_driver.is_active)
    self.assertEqual(test_driver._use_count, 0)
  
  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}
