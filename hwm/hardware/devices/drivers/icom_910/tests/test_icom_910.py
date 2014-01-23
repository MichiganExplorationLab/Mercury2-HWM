# Import required modules
import logging, time
import mock
import Hamlib
from mock import MagicMock, patch
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from hwm.core.configuration import *
from hwm.command import command
from hwm.hardware.pipelines import pipeline
from hwm.hardware.devices.drivers.icom_910 import icom_910

class TestIcom910(unittest.TestCase):
  """ This test suite verifies the functionality of the ICOM 910 driver.

  @note The ICOM 910 driver depends on Hamlib and its Python bindings. To minimize testing dependencies, Hamlib APIs 
        will be mocked when possible during the tests in this module (although the Hamlib module is still required).
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.standard_icom_config = {'id': "icom_910", 'settings': {'icom_device_path': "/dev/ttySO", 'doppler_update_frequency': 5, 'doppler_update_inactive_tx_delay': 1}}
    
    # Mock the Hamlib.rig_set_debug function
    self.old_rig_set_debug = Hamlib.rig_set_debug
    Hamlib.rig_set_debug = MagicMock()

    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()

    # Restore rig_set_debug
    Hamlib.rig_set_debug = self.old_rig_set_debug
    
    # Reset the configuration reference
    self.config = None

  def test_driver_init(self):
    """ Tests that the ICOM 910 driver constructor puts the driver into the correct state in preparation for a new 
    session. As a result, it also tests that the reset_driver_state method is working as intended. """

    # Initialize a test driver
    test_cp = MagicMock()
    test_device = icom_910.ICOM_910(self.standard_icom_config, test_cp)

    # Verify that the device was set up correctly
    self.assertEqual(test_device.icom_device_path, self.standard_icom_config['settings']['icom_device_path'])
    self.assertEqual(test_device.doppler_update_frequency, self.standard_icom_config['settings']['doppler_update_frequency'])
    self.assertEqual(test_device.doppler_update_inactive_tx_delay, self.standard_icom_config['settings']['doppler_update_inactive_tx_delay'])
    self.assertEqual(test_device._tracker_service, None)
    self.assertEqual(test_device._tnc_state_service, None)
    self.assertTrue(len(test_device._radio_state) > 0)

  @patch("Hamlib.Rig")
  def test_prepare_for_session(self, mocked_Hamlib):
    """ Makes sure that the driver can prepare for a new useage session. """

    # Initialize a test driver
    test_cp = MagicMock()
    test_device = icom_910.ICOM_910(self.standard_icom_config, test_cp)

    # Create a mock pipeline that returns mock services
    test_pipeline = MagicMock()
    mock_tnc_state_service = MagicMock()
    mock_tracker_service = MagicMock()
    def mock_load_service(service_id):
      if service_id == "tnc_state":
        return mock_tnc_state_service
      else:
        return mock_tracker_service
    test_pipeline.load_service = mock_load_service

    # Prepare for the session and verify results
    results = test_device.prepare_for_session(test_pipeline)
    self.assertTrue(results)
    self.assertEqual(test_device._session_pipeline, test_pipeline)
    self.assertEqual(test_device._tracker_service, mock_tracker_service)
    self.assertEqual(test_device._tnc_state_service, mock_tnc_state_service)
    test_device._tracker_service.register_position_receiver.assert_called_once_with(test_device.process_new_doppler_correction)
    self.assertEqual(Hamlib.rig_set_debug.call_count, 1)
    mocked_Hamlib().set_conf.assert_has_calls([mock.call("rig_pathname", self.standard_icom_config['settings']['icom_device_path']),
                                               mock.call("retry", "5")])
    mocked_Hamlib().open.assert_called_once_with()

  @patch("Hamlib.Rig")
  def test_prepare_for_session_missing_service(self, mocked_Hamlib):
    """ Verifies that the driver still prepares itself for new sessions if it can't find any services that it is capable
    of using. """

    # Initialize a test driver
    test_cp = MagicMock()
    test_device = icom_910.ICOM_910(self.standard_icom_config, test_cp)

    # Create a mock pipeline that doesn't return any services
    test_pipeline = MagicMock()
    test_pipeline.load_service = MagicMock(side_effect=pipeline.ServiceTypeNotFound)

    # Prepare for the session
    results = test_device.prepare_for_session(test_pipeline)
    self.assertEqual(test_device._tracker_service, None)
    self.assertEqual(test_device._tnc_state_service, None)

    # Make sure the radio was still setup (shouldn't depend on services)
    self.assertEqual(Hamlib.rig_set_debug.call_count, 1)
    mocked_Hamlib().set_conf.assert_has_calls([mock.call("rig_pathname", self.standard_icom_config['settings']['icom_device_path']),
                                               mock.call("retry", "5")])
    mocked_Hamlib().open.assert_called_once_with()

  @patch("Hamlib.Rig")
  def test_cleanup_after_session(self, mocked_Hamlib):
    """ Makes sure that the driver correctly cleans up after the session using it ends. """

    # Initialize a test driver
    test_cp = MagicMock()
    test_device = icom_910.ICOM_910(self.standard_icom_config, test_cp)

    # Create a mock pipeline that returns mock services
    test_pipeline = MagicMock()
    mock_tnc_state_service = MagicMock()
    mock_tracker_service = MagicMock()
    def mock_load_service(service_id):
      if service_id == "tnc_state":
        return mock_tnc_state_service
      else:
        return mock_tracker_service
    test_pipeline.load_service = mock_load_service

    # Prepare for the session
    results = test_device.prepare_for_session(test_pipeline)
    self.assertEqual(test_device._tracker_service, mock_tracker_service)
    self.assertEqual(test_device._tnc_state_service, mock_tnc_state_service)

    # Clean up after the session and make sure it had the intended effect
    test_device.cleanup_after_session()
    mocked_Hamlib().close.assert_called_once_with()
    self.assertEqual(test_device._tracker_service, None)
    self.assertEqual(test_device._tnc_state_service, None)

  @inlineCallbacks
  def test_process_new_doppler_correction(self):
    """ Verifies that the process_new_position() callback correctly responds to new doppler correction information. """

    # Create a test pipeline
    test_pipeline = MagicMock()
    test_pipeline.id = "test_pipeline"
    test_pipeline.current_session.user_id = "test_user"

    def mock_parse_command(command_request, **keywords):
      if command_request['command'] == "set_rx_freq":
        self.assertEqual(command_request['parameters']['frequency'], 5)
      elif command_request['command'] == "set_tx_freq":
        self.assertEqual(command_request['parameters']['frequency'], 25)

      return defer.succeed({'response':{'status':'okay'}})

    # Create a test Icom driver
    test_cp = MagicMock()
    test_cp.parse_command = mock_parse_command
    test_device = icom_910.ICOM_910(self.standard_icom_config, test_cp)
    test_device._session_pipeline = test_pipeline
    test_device._radio_state['set_rx_freq'] = 20
    test_device._radio_state['set_tx_freq'] = 100

    # Create a mock target_position and submit it
    doppler_correction = {
      "doppler_multiplier": 0.25
    }
    test_deferred = test_device.process_new_doppler_correction(doppler_correction)
    results = yield test_deferred

    # Verify result
    self.assertTrue(results)
    self.assertTrue(test_device._last_doppler_update > 0)

  @inlineCallbacks
  def test_process_new_doppler_correction_error(self):
    """ Verifies that the ICOM driver can handle any errors that may occur while responding to the doppler correction.
    """

    # Create a test pipeline
    test_pipeline = MagicMock()
    test_pipeline.id = "test_pipeline"
    test_pipeline.current_session.user_id = "test_user"

    def mock_parse_command(command_request, **keywords):
      if command_request['command'] == "set_rx_freq":
        return defer.succeed({'response':{'status':'okay'}})
      elif command_request['command'] == "set_tx_freq":
        return defer.succeed({'response':{'status':'error'}})

    # Create a test Icom driver
    test_cp = MagicMock()
    test_cp.parse_command = mock_parse_command
    test_device = icom_910.ICOM_910(self.standard_icom_config, test_cp)
    test_device._session_pipeline = test_pipeline
    test_device._radio_state['set_downlink_freq'] = 20
    test_device._radio_state['set_uplink_freq'] = 100

    # First submit an invalid doppler correction
    doppler_correction = {
      "ya_dun_goofed": True
    }
    test_deferred = test_device.process_new_doppler_correction(doppler_correction)
    results = yield test_deferred

    # Verify results and submit a valid doppler correction
    self.assertTrue(not results)
    doppler_correction = {
      "doppler_multiplier": 0.25
    }
    test_deferred = test_device.process_new_doppler_correction(doppler_correction)
    results = yield test_deferred

    # Make sure the update failed (due to a failed set_tx_freq command)
    self.assertTrue(not results)
    self.assertEqual(test_device._last_doppler_update, 0)

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestICOM910Handler(unittest.TestCase):
  """ Tests the functionality of the ICOM 910's command handler class.
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    
    # Mock the Hamlib.rig_set_debug function
    self.old_rig_set_debug = Hamlib.rig_set_debug
    Hamlib.rig_set_debug = MagicMock()

    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()

    # Restore rig_set_debug
    Hamlib.rig_set_debug = self.old_rig_set_debug
    
    # Reset the configuration reference
    self.config = None

  def test_set_mode_command(self):
    """ Tests the functionality of the 'set_mode' command. """

    # Create a command handler to test with
    test_command = MagicMock()
    test_device = MagicMock()
    test_device._radio_state = {}
    test_handler = icom_910.ICOM910Handler(test_device)

    def mock_rig_strrmode(mode):
      self.assertEqual(mode, "FM")
      return "FM"

    # Setup a mock rig and submit a test command
    Hamlib.rig_strrmode = mock_rig_strrmode
    test_handler.radio_rig = MagicMock()
    test_handler.radio_rig.set_mode = lambda mode : Hamlib.RIG_OK
    test_handler.radio_rig.get_mode = lambda : ("FM", 10)
    test_command.parameters = {'mode': "FM"}
    results = test_handler.command_set_mode(test_command)

    # Check results
    self.assertEqual(test_device._radio_state['mode'], "FM")
    self.assertEqual(results['message'], "The radio mode has been set.")

  def test_set_mode_command_errors(self):
    """ Verifies that the 'set_mode' command can correctly handle various errors. """

    # Create a command handler to test with
    test_command = MagicMock()
    test_device = MagicMock()
    test_handler = icom_910.ICOM910Handler(test_device)

    # First try executing the command without a Hamlib rig
    test_command = MagicMock()
    self.assertRaises(command.CommandError, test_handler.command_set_mode, test_command)

    # Setup a mock rig and submit a command that doesn't include a mode
    test_handler.radio_rig = MagicMock()
    test_command.parameters = {'missing_mode': True}
    self.assertRaises(command.CommandError, test_handler.command_set_mode, test_command)

    # Submit a command that specifies an urecognized mode
    test_command.parameters = {'mode': "FMX"}
    self.assertRaises(command.CommandError, test_handler.command_set_mode, test_command)

    # Submit a command that causes Hamlib to fail
    test_handler.radio_rig.set_mode = lambda mode : Hamlib.RIG_DEBUG_ERR
    test_command.parameters = {'mode': "FM"}
    self.assertRaises(command.CommandError, test_handler.command_set_mode, test_command)

  def test_set_rx_freq(self):
    """ Tests the functionality of the 'set_rx_freq' command. """

    # Create a command handler to test with
    freq_mult = 1000000
    test_command = MagicMock()
    test_device = MagicMock()
    test_device._radio_state = {'shifted_rx_freq': 0, 'set_rx_freq': 0}
    test_handler = icom_910.ICOM910Handler(test_device)

    # Setup a mock rig and submit a command which should set the initial frequency
    test_handler.radio_rig = MagicMock()
    test_handler.radio_rig.get_freq = lambda : 10 * freq_mult # Convert to Hz from Mhz like Hamlib does
    test_handler.radio_rig.set_freq = lambda freq, vfo : Hamlib.RIG_OK
    test_command.parameters = {'rx_freq': 10}
    results = test_handler.command_set_rx_freq(test_command)

    # Check results and submit another command which simulates a doppler correction
    self.assertEqual(test_device._radio_state['shifted_rx_freq'], 0)
    self.assertEqual(test_device._radio_state['set_rx_freq'], 10 * freq_mult)
    self.assertEqual("The radio's RX frequency has been set.", results['message'])
    self.assertEqual(results['frequency'], 10)
    test_handler.radio_rig.get_freq = lambda : 5 * freq_mult
    test_command.parameters = {'rx_freq': 5}
    results = test_handler.command_set_rx_freq(test_command)

    # Verify results
    self.assertEqual(test_device._radio_state['shifted_rx_freq'], 5 * freq_mult)
    self.assertEqual(test_device._radio_state['set_rx_freq'], 10 * freq_mult)
    self.assertEqual("The radio's RX frequency has been set.", results['message'])
    self.assertEqual(results['frequency'], 5)

  def test_set_rx_freq_errors(self):
    """ Verifies that the 'set_rx_freq' command can correctly handle various errors. """

    # Create a command handler to test with
    test_command = MagicMock()
    test_device = MagicMock()
    test_handler = icom_910.ICOM910Handler(test_device)

    # First try executing the command without a Hamlib rig
    test_command = MagicMock()
    self.assertRaises(command.CommandError, test_handler.command_set_rx_freq, test_command)

    # Setup a mock rig and submit a command that doesn't include a frequency
    test_handler.radio_rig = MagicMock()
    test_command.parameters = {'missing_rx_freq': True}
    self.assertRaises(command.CommandError, test_handler.command_set_rx_freq, test_command)

    # Submit a command that causes Hamlib to fail
    test_handler.radio_rig.set_freq = lambda freq, vfo : Hamlib.RIG_DEBUG_ERR
    test_command.parameters = {'rx_freq': 10}
    self.assertRaises(command.CommandError, test_handler.command_set_rx_freq, test_command)

  def test_set_tx_freq(self):
    """ Tests the functionality of the 'set_tx_freq' command. """

    # Create a command handler to test with
    freq_mult = 1000000
    test_command = MagicMock()
    test_device = MagicMock()
    test_device._radio_state = {'shifted_tx_freq': 0, 'set_tx_freq': 0}
    test_device.doppler_update_inactive_tx_delay = 2 # s
    mock_tnc_state = {'last_transmitted': int(time.time())-test_device.doppler_update_inactive_tx_delay*2, 'output_buffer_size_bytes': 0}
    test_device._tnc_state_service.get_state = lambda : mock_tnc_state
    test_handler = icom_910.ICOM910Handler(test_device)

    # Setup a mock rig and submit a command which should set the initial frequency
    test_handler.radio_rig = MagicMock()
    test_handler.radio_rig.get_split_freq = lambda : 10 * freq_mult # Convert to Hz from Mhz like Hamlib does
    test_handler.radio_rig.set_split_freq = lambda vfo, freq : Hamlib.RIG_OK
    test_command.parameters = {'tx_freq': 10}
    results = test_handler.command_set_tx_freq(test_command)

    # Check results and submit another command which simulates a doppler correction
    self.assertEqual(test_device._radio_state['shifted_tx_freq'], 0)
    self.assertEqual(test_device._radio_state['set_tx_freq'], 10 * freq_mult)
    self.assertEqual("The radio's TX frequency has been set using a split.", results['message'])
    self.assertEqual(results['frequency'], 10)
    test_handler.radio_rig.get_split_freq = lambda : 5 * freq_mult
    test_command.parameters = {'tx_freq': 5}
    results = test_handler.command_set_tx_freq(test_command)

    # Verify results
    self.assertEqual(test_device._radio_state['shifted_tx_freq'], 5 * freq_mult)
    self.assertEqual(test_device._radio_state['set_tx_freq'], 10 * freq_mult)
    self.assertEqual("The radio's TX frequency has been set using a split.", results['message'])
    self.assertEqual(results['frequency'], 5)

  def test_set_tx_freq_errors(self):
    """ Verifies that the 'set_tx_freq' command can correctly handle various errors. """

    # Create a command handler to test with
    test_command = MagicMock()
    test_device = MagicMock()
    test_device.doppler_update_inactive_tx_delay = 2 # s
    mock_tnc_state = {'last_transmitted': int(time.time())-test_device.doppler_update_inactive_tx_delay*2, 'output_buffer_size_bytes': 20}
    test_device._tnc_state_service.get_state = lambda : mock_tnc_state
    test_handler = icom_910.ICOM910Handler(test_device)

    # First try executing the command without a Hamlib rig
    test_command = MagicMock()
    self.assertRaises(command.CommandError, test_handler.command_set_tx_freq, test_command)

    # Setup a mock rig and submit a command that doesn't include a frequency
    test_handler.radio_rig = MagicMock()
    test_command.parameters = {'missing_tx_freq': True}
    self.assertRaises(command.CommandError, test_handler.command_set_tx_freq, test_command)

    # Submit a command that fails because TNC is writing data
    test_command.parameters = {'tx_freq': 10}
    self.assertRaises(command.CommandError, test_handler.command_set_tx_freq, test_command)

    # Submit a command that fails because the TNC was recently written to
    mock_tnc_state['last_transmitted'] = int(time.time()) - 1
    mock_tnc_state['output_buffer_size_bytes'] = 0
    test_command.parameters = {'tx_freq': 10}
    self.assertRaises(command.CommandError, test_handler.command_set_tx_freq, test_command)

    # Submit a command that causes Hamlib to fail
    mock_tnc_state['last_transmitted'] = int(time.time()) - test_device.doppler_update_inactive_tx_delay*2
    test_handler.radio_rig.set_split_freq = lambda vfo, freq : Hamlib.RIG_DEBUG_ERR
    test_command.parameters = {'tx_freq': 10}
    self.assertRaises(command.CommandError, test_handler.command_set_tx_freq, test_command)

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

