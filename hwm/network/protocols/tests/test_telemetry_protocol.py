# Import required modules
import logging, json, base64, exceptions
from mock import MagicMock
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from twisted.test import proto_helpers
from hwm.network.protocols import telemetry
from hwm.sessions import session

class TestPipelineTelemetryProtocol(unittest.TestCase):
  """ This test suite is designed to test the functionality of the PipelineTelemetry protocol, which is responsible for 
  routing the various pipeline telemetry streams to the end user (typically through the user interface).
  """
  
  def setUp(self):
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Create a PipelineTelemetryFactory with a mock session coordinator and build the test resources
    self.session_coordinator = MagicMock()
    protocol_factory = telemetry.PipelineTelemetryFactory(self.session_coordinator)
    self.protocol = protocol_factory.buildProtocol(('127.0.0.1', 0))
    self.old_connectionMade = self.protocol.connectionMade
    self.protocol.connectionMade = self._mock_connectionMade
    self.transport = proto_helpers.StringTransport()
    self.protocol.makeConnection(self.transport)

    # Disable logging for most events
    logging.disable(logging.CRITICAL)

  def test_sending_pipeline_telemetry(self):
    """ This test verifies that the protocol can correctly relay any pipeline telemetry that it receives to the pipeline
    user. In addition, it validates the format of the telemetry data that gets passed to the network.
    """

    # Write some telemetry data to the protocol and make sure it was properly formatted when received
    telem_point = {
      "source": "test_source",
      "stream": "test_stream",
      "generated_at": 42,
      "binary": False,
      "telemetry": "just some telemetry",
    }
    self.protocol.write_telemetry(telem_point['source'], telem_point['stream'],
                                  telem_point['generated_at'], telem_point['telemetry'])
    received_dictionary = json.loads(self.transport.value())
    self.assertEqual(telem_point, received_dictionary)
    self.transport.clear()

    # Now try sending a telemetry data point that contains some extra headers
    telem_point = {
      "source": "test_source",
      "stream": "test_stream",
      "generated_at": 42,
      "binary": False,
      "telemetry": "just some telemetry",
      "test_header": True,
      "test_header_2": "just some metadata"
    }
    self.protocol.write_telemetry(telem_point['source'], telem_point['stream'],
                                  telem_point['generated_at'], telem_point['telemetry'],
                                  test_header=telem_point['test_header'], test_header_2=telem_point['test_header_2'])
    received_dictionary = json.loads(self.transport.value())
    self.assertEqual(received_dictionary, telem_point)

  def test_sending_pipeline_telemetry_binary(self):
    """ Tests that the protocol can send binary telemetry data over the network. By setting the "binary" argument to 
    true when writing telemetry to the session, pipelines and devices can send binary data like images and audio clips 
    to the pipeline user.
    """

    # Load a small test image and convert it into a string
    test_image = open(self.source_data_directory+"/network/protocols/tests/data/mxl_logo.png", "rb")
    test_image_str = test_image.read()
    test_image.close()

    # Construct the telemetry point
    telem_point = {
      "source": "test_source",
      "stream": "test_stream",
      "generated_at": 58,
      "binary": True,
      "telemetry": test_image_str,
      "test_header": True,
      "test_header_2": "just some metadata"
    }
    self.protocol.write_telemetry(telem_point['source'], telem_point['stream'], telem_point['generated_at'], 
                                  telem_point['telemetry'], binary=telem_point['binary'],
                                  test_header=telem_point['test_header'], test_header_2=telem_point['test_header_2'])
    received_dictionary = json.loads(self.transport.value())
    telem_point['telemetry'] = base64.b64encode(telem_point['telemetry'])
    self.assertEqual(received_dictionary, telem_point)
    self.assertEqual(base64.b64decode(received_dictionary['telemetry']), test_image_str)

  def test_protocol_registrations(self):
    """ This test verifies that the PipelineTelemetry.perform_registrations() callback correctly registers the 
    Protocol with the necessary resources and that it correctly handles possible errors.
    """

    # Create a mock session
    test_session = MagicMock()
    self.protocol.transport.registerProducer = MagicMock()

    # Register with the mock session
    self.protocol.perform_registrations(test_session)
    test_session.register_telemetry_protocol.assert_called_once_with(self.protocol)
    self.assertEqual(self.protocol.session, test_session)

    # Make sure the protocol loaded and registered the pipeline's telemetry producer (via the session)
    test_session.get_pipeline_telemetry_producer.assert_called_once_with()
    self.assertEqual(self.protocol.transport.registerProducer.call_count, 1)

    # Replace register_data_protocol with a mock version that will generate an exception
    test_session.register_telemetry_protocol = self._mock_session_protocol_registration
    self.assertRaises(session.ProtocolAlreadyRegistered, self.protocol.perform_registrations, test_session)

  def test_initial_session_lookup_session_not_found(self):
    """ This test verifies that the telemetry protocol correctly handles errors that may occur when setting up the 
    connection such as an invalid session.
    """

    # Create a mock protocol and session to test with
    test_res_id = "res_id"
    test_session = MagicMock()
    self.protocol.connectionMade = self.old_connectionMade # Restore the actual connectionMade method for this test
    self.protocol.transport.getPeerCertificate = lambda : None
    self.protocol.transport.abortConnection = MagicMock()
    self.protocol.session_coordinator.load_reservation_session = self._mock_session_lookup_failed

    def validate_session(loaded_session):
      """ A callback that will be called after the protocol has handled the session lookup error.
      """

      self.assertEqual(loaded_session, None)
      self.assertEqual(self.protocol.session, None)
      self.protocol.transport.abortConnection.assert_called_once_with()

    # Simulate a newly initialized connection
    setup_deferred = self.protocol.connectionMade()
    setup_deferred.addCallback(validate_session)

    # Update the getPeerCertificate method to return a valid mock certificate before the reactor.callLater call goes out
    test_cert = MagicMock()
    test_subject = MagicMock()
    test_subject.commonName = test_res_id
    test_cert.get_subject = lambda : test_subject
    self.protocol.transport.getPeerCertificate = lambda : test_cert

    return setup_deferred

  def test_initial_session_lookup(self):
    """ This test verifies that the telemetry protocol can load the requested session and perform the necessary 
    registrations when the user connection is made via it's connectionMade() callback.
    """

    # Create a mock protocol and session to test with
    test_res_id = "res_id"
    test_session = MagicMock()
    self.protocol.connectionMade = self.old_connectionMade # Restore the actual connectionMade method for this test
    self.protocol.transport.registerProducer = MagicMock()
    self.protocol.transport.getPeerCertificate = lambda : None
    self.protocol.session_coordinator.load_reservation_session = lambda res_id: test_session

    def validate_session(loaded_session):
      """ A callback that will receive the session once the simulated TLS handshake finishes.
      """

      self.assertEqual(loaded_session, test_session)
      self.assertEqual(self.protocol.session, test_session)
      test_session.register_telemetry_protocol.assert_called_once_with(self.protocol)
      test_session.get_pipeline_telemetry_producer.assert_called_once_with()
      self.assertEqual(self.protocol.transport.registerProducer.call_count, 1)

    # Simulate a newly initialized connection
    setup_deferred = self.protocol.connectionMade()
    setup_deferred.addCallback(validate_session)

    # Update the getPeerCertificate method to return a valid mock certificate before the reactor.callLater call goes out
    test_cert = MagicMock()
    test_subject = MagicMock()
    test_subject.commonName = test_res_id
    test_cert.get_subject = lambda : test_subject
    self.protocol.transport.getPeerCertificate = lambda : test_cert

    return setup_deferred


  def _mock_connectionMade(self):
    """ A mock version of the PipelineData Protocol that does not call the AuthUtilities._wait_for_session mixin. This
    is required because the proto_helpers.StringTransport() transport we're testing with doesn't support SSL. In
    addition, the callLater() call in _wait_for_session() would make test cleanup more difficult.
    """

    return

  def _mock_session_protocol_registration(self, protocol):
    """ Simulates a duplicate telemetry protocol registration on a Session by throwing the ProtocolAlreadyRegistered
    exception.

    @throw Always throws session.ProtocolAlreadyRegistered.
    """

    raise session.ProtocolAlreadyRegistered("Testing session-telemetry protocol registration.")

  def _mock_session_lookup_failed(self, res_id):
    """ This function raises a coordinator.SessionNotFound exception and is used to test error handling.
    """

    raise coordinator.SessionNotFound("Test SessionNotFound exception.")
