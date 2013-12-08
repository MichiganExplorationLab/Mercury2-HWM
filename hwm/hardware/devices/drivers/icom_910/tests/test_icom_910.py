# Import required modules
import logging, time
import mock
import Hamlib
from mock import MagicMock, patch
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from hwm.core.configuration import *
from hwm.hardware.pipelines import pipeline
from hwm.hardware.devices.drivers.icom_910 import icom_910

class TestIcom910(unittest.TestCase):
  """ This test suite verifies the functionality of the ICOM 910 driver.

  @note The ICOM 910 driver depends on Hamlib and its Python bindings. To minimize testing dependencies, Hamlib APIs 
        will be mocked when possible during these tests (although the Hamlib module is still required).
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.standard_tnc_config = {'id': "icom_910", 'icom_device_path': "/dev/ttySO", 'doppler_update_frequency': 5, 'doppler_update_inactive_tx_delay': 1}
    
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
    test_device = icom_910.ICOM_910(self.standard_tnc_config, test_cp)

    # Verify that the device was set up correctly
    self.assertEqual(test_device.icom_device_path, self.standard_tnc_config['icom_device_path'])
    self.assertEqual(test_device.doppler_update_frequency, self.standard_tnc_config['doppler_update_frequency'])
    self.assertEqual(test_device.doppler_update_inactive_tx_delay, self.standard_tnc_config['doppler_update_inactive_tx_delay'])
    self.assertEqual(test_device._tracker_service, None)
    self.assertEqual(test_device._tnc_state_service, None)
    self.assertTrue(len(test_device._radio_state) > 0)

  @patch("Hamlib.Rig")
  def test_prepare_for_session(self, mocked_Hamlib):
    """ Makes sure that the driver can prepare for a new useage session. """

    # Initialize a test driver
    test_cp = MagicMock()
    test_device = icom_910.ICOM_910(self.standard_tnc_config, test_cp)

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
    mocked_Hamlib().set_conf.assert_has_calls([mock.call("rig_pathname", self.standard_tnc_config['icom_device_path']),
                                               mock.call("retry", "5")])
    mocked_Hamlib().open.assert_called_once_with()

  @patch("Hamlib.Rig")
  def test_prepare_for_session_missing_service(self, mocked_Hamlib):
    """ Verifies that the driver still prepares itself for new sessions if it can't find any services that it is capable
    of using. """

    # Initialize a test driver
    test_cp = MagicMock()
    test_device = icom_910.ICOM_910(self.standard_tnc_config, test_cp)

    # Create a mock pipeline that doesn't return any services
    test_pipeline = MagicMock()
    test_pipeline.load_service = MagicMock(side_effect=pipeline.ServiceTypeNotFound)

    # Prepare for the session
    results = test_device.prepare_for_session(test_pipeline)
    self.assertEqual(test_device._tracker_service, None)
    self.assertEqual(test_device._tnc_state_service, None)

    # Make sure the radio was still setup (shouldn't depend on services)
    self.assertEqual(Hamlib.rig_set_debug.call_count, 1)
    mocked_Hamlib().set_conf.assert_has_calls([mock.call("rig_pathname", self.standard_tnc_config['icom_device_path']),
                                               mock.call("retry", "5")])
    mocked_Hamlib().open.assert_called_once_with()

  @patch("Hamlib.Rig")
  def test_cleanup_after_session(self, mocked_Hamlib):
    """ Makes sure that the driver correctly cleans up after the session using it ends. """

    # Initialize a test driver
    test_cp = MagicMock()
    test_device = icom_910.ICOM_910(self.standard_tnc_config, test_cp)

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
      return defer.succeed({'response':{'status':'okay'}})

    # Create a test Icom driver
    test_cp = MagicMock()
    test_cp.parse_command = mock_parse_command
    test_device = icom_910.ICOM_910(self.standard_tnc_config, test_cp)
    test_device._session_pipeline = test_pipeline
    test_device._radio_state['set_downlink_freq'] = 20
    test_device._radio_state['set_uplink_freq'] = 100

    # Create a mock target_position and submit it
    doppler_correction = {
      "doppler_multiplier": 0.25
    }
    test_deferred = test_device.process_new_doppler_correction(doppler_correction)
    results = yield test_deferred
    print results

    # Verify result
    self.assertTrue(results)
    self.assertTrue(test_device._last_doppler_update > 0)
    print test_cp.parse_command.mock_calls

  #def test_process_new_doppler_correction_error(self):

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}