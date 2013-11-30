# Import required modules
import logging, time
from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks
from mock import MagicMock
from pkg_resources import Requirement, resource_filename
from StringIO import StringIO
from hwm.core.configuration import *
from hwm.command import command
from hwm.hardware.devices.drivers.sgp4_tracker import sgp4_tracker

class TestSGP4Tracker(unittest.TestCase):
  """ This test suite verifies the functionality of the SGP4 tracker virtual driver.
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')
    self.standard_device_config = {'id': "test_device", 'propagation_frequency': 2}
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_prepare_for_session(self):
    """ This test verifies that the SGP4 virtual driver takes the correct actions in preparation for a new session.
    """

    # Initialize the device
    test_pipeline = MagicMock()
    test_device = sgp4_tracker.SGP4TrackerDriver(self.standard_device_config, MagicMock())
    test_device._propagation_service = MagicMock()
    test_device._propagation_service.id = "sgp4_test_service"
    test_device._propagation_service.type = "tracker"

    # Verify that the device can register services and initialize its command handler
    test_device.register_pipeline(test_pipeline)
    test_pipeline.register_service.assert_called_once_with(test_device._propagation_service)
    self.assertTrue(isinstance(test_device._command_handler, sgp4_tracker.SGP4Handler))

    # Run the prepare_for_session callback and check results
    test_device.prepare_for_session(test_pipeline)
    test_device._propagation_service.start_tracker.assert_called_once_with()

  def test_cleanup_after_session(self):
    """ This test verifies that the SGP4 virtual driver can correctly cleanup after the session using it has ended. """

    # Initialize the device
    test_pipeline = MagicMock()
    test_device = sgp4_tracker.SGP4TrackerDriver(self.standard_device_config, MagicMock())
    test_device._reset_tracker_state = MagicMock()
    test_device._propagation_service = MagicMock()

    # Run the prepare_for_session callback and check results
    test_device.cleanup_after_session()
    test_device._propagation_service.reset_tracker.assert_called_once_with()
    test_device._reset_tracker_state.assert_called_once_with()

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestSGP4Handler(unittest.TestCase):
  """ This test suite verifies the functionality of the SGP4 virtual driver's command handler.
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_start_tracking_command(self):
    """ Tests the 'start_tracking' command and possible errors.
    """

    # Initialize a test command handler with a mock driver
    test_command = MagicMock()
    test_driver = MagicMock()
    test_driver._propagation_service.start_tracker = lambda : None
    test_handler = sgp4_tracker.SGP4Handler(test_driver)

    # Run the command with a simulated tracker event loop already running
    self.assertRaises(command.CommandError, test_handler.command_start_tracking, test_command)

    # Run the command without a simulated tracker running
    test_driver._propagation_service.start_tracker = lambda : True
    results = test_handler.command_start_tracking(test_command)
    self.assertTrue("has been started." in results['message'])

  def test_stop_tracking_command(self):
    """ Tests the 'stop_tracking' command and possible errors.
    """

    # Initialize a test command handler with a mock driver
    test_command = MagicMock()
    test_driver = MagicMock()
    test_driver._propagation_service._propagation_loop = MagicMock()
    test_driver._propagation_service._propagation_loop.running = True
    test_handler = sgp4_tracker.SGP4Handler(test_driver)

    # Run the command with a simulated tracker event loop already running
    results = test_handler.command_stop_tracking(test_command)
    test_driver._propagation_service._propagation_loop.stop.assert_called_once_with()
    self.assertTrue("has been stopped." in results['message'])

    # Run the command without a simulated tracker not running
    test_driver._propagation_service._propagation_loop = None
    self.assertRaises(command.CommandError, test_handler.command_stop_tracking, test_command)

  def test_set_target_tle_command(self):
    """ Tests the 'target_tle_command' command and possible errors.
    """

    # Initialize a test command handler with a command that doesn't specify any parameters
    test_command = MagicMock()
    test_command.parameters = {'line_1': "test TLE line"}
    test_driver = MagicMock()
    test_handler = sgp4_tracker.SGP4Handler(test_driver)

    # Make sure the command fails if the command did not include the required TLE information
    self.assertRaises(command.CommandError, test_handler.command_set_target_tle, test_command)

    # Test a successful command
    test_command.parameters = {'line_1': "Test TLE Line 1",'line_2': "Test TLE Line 2"}
    results = test_handler.command_set_target_tle(test_command)
    test_driver._propagation_service.set_tle.assert_called_once_with("Test TLE Line 1", "Test TLE Line 2")

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestSGP4TrackingService(unittest.TestCase):
  """ This test suite is designed to test the functionality of the SGP4 tracking service.
  """
  
  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')
    self.standard_device_config = {'id': "test_device", 'propagation_frequency': 2}
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_service_initialization(self):
    """ Tests that the tracking service correctly initializes its state when constructed.
    """

    # Create a service to test with
    test_service = sgp4_tracker.SGP4PropagationService('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    # Verify the service's attributes
    self.assertEqual(test_service._station_longitude, -83.71264)
    self.assertEqual(test_service._station_latitude, 42.29364)
    self.assertEqual(test_service._station_altitude, 276)
    self.assertEqual(test_service._TLE_line_1, None)
    self.assertEqual(test_service._TLE_line_2, None)
    self.assertEqual(test_service._satellite, None)
    self.assertEqual(test_service._propagation_loop, None)
    self.assertEqual(len(test_service._registered_handlers), 0)

  def test_propagate_tle(self):
    """ Tests the _propagate_tle() method which is responsible for performing one round of propagation and sending the 
    new position data to the registered position data handlers. """

    # Mock time to return a known time
    old_time = time.time
    time.time = lambda : 1385438844
    
    # Create a service to test with
    test_service = sgp4_tracker.SGP4PropagationService('direct_downlink_aprs_service', 'tracker', self.standard_device_config)
    test_service.set_tle("1 37853U 11061D   13328.80218348  .00012426  00000-0  90147-3 0  6532",
                         "2 37853 101.7000 256.9348 0228543 286.4751 136.0421 14.85566785112276")

    # Register a mock position receiver
    results = None
    def test_receiver(targetting_info):
      results = targetting_info
    test_receiver2 = MagicMock()
    test_service.register_position_receiver(test_receiver)
    test_service.register_position_receiver(test_receiver2)

    # Run the propagator and verify the results
    results = test_service._propagate_tle()
    test_receiver2.assert_called_once_with(results)
    self.assertEqual(results['timestamp'], 1385438844)
    self.assertEqual(results['altitude'], 643468.9375)
    self.assertEqual(results['elevation'], -41.31524396861143)
    self.assertEqual(results['azimuth'], 111.91629687167571)
    self.assertEqual(results['latitude'], -0.9842437063337659)
    self.assertEqual(results['longitude'], -48.365802362005475)

    # Restore the time module
    time.time = old_time

  @inlineCallbacks
  def test_start_tracker(self):
    """ Makes sure the propagation service can start successfully. """

    # Create a service to test with
    test_service = sgp4_tracker.SGP4PropagationService('direct_downlink_aprs_service', 'tracker', self.standard_device_config)
    test_service.set_tle("1 37853U 11061D   13328.80218348  .00012426  00000-0  90147-3 0  6532",
                         "2 37853 101.7000 256.9348 0228543 286.4751 136.0421 14.85566785112276")

    # Overload the propagation method to fail
    test_service._propagate_tle = MagicMock()

    # Start the service
    test_deferred = test_service.start_tracker()
    self.assertTrue(test_service._propagation_loop.running)
    test_service._propagation_loop.stop()
    result = yield test_deferred

    test_service._propagate_tle.assert_called_once_with()

  @inlineCallbacks
  def test_start_tracker_error(self):
    """ Tests that the propagation service can correctly handle errors that may occur while propagating. """

    # Create a service to test with
    test_service = sgp4_tracker.SGP4PropagationService('direct_downlink_aprs_service', 'tracker', self.standard_device_config)
    test_service.set_tle("1 37853U 11061D   13328.80218348  .00012426  00000-0  90147-3 0  6532",
                         "2 37853 101.7000 256.9348 0228543 286.4751 136.0421 14.85566785112276")

    # Overload the propagation method to fail
    def mock_failure():
      raise TypeError("Ya blew it.")
    test_service._propagate_tle = mock_failure

    # Start the service
    test_deferred = test_service.start_tracker()
    result = yield test_deferred

    # Make sure the error was handled
    self.assertEqual(result, False)
    self.assertTrue(not test_service._propagation_loop.running)

  @inlineCallbacks
  def test_reset_tracker(self):
    """ Verify that the propagation service can be reset successfully. """

    # Create a service to test with
    test_service = sgp4_tracker.SGP4PropagationService('direct_downlink_aprs_service', 'tracker', self.standard_device_config)
    test_service.set_tle("1 37853U 11061D   13328.80218348  .00012426  00000-0  90147-3 0  6532",
                         "2 37853 101.7000 256.9348 0228543 286.4751 136.0421 14.85566785112276")
    test_service._reset_propagator_state = MagicMock()

    # Reset the tracker before a loop has been created
    test_service.reset_tracker()
    self.assertEqual(test_service._propagation_loop, None)
    test_service._reset_propagator_state.assert_called_once_with()

    # Start the service
    test_deferred = test_service.start_tracker()
    test_service.reset_tracker()
    result = yield test_deferred

    # Verify results
    self.assertTrue(not test_service._propagation_loop.running)
    self.assertEqual(test_service._reset_propagator_state.call_count, 2)

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}