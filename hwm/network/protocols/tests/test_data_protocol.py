# Import required modules
import logging
from mock import MagicMock
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from twisted.test import proto_helpers
from hwm.network.protocols import data
from hwm.sessions import session, coordinator

class TestPipelineDataProtocol(unittest.TestCase):
  """ This test suite is designed to test the functionality of the PipelineData protocol, which is responsible for 
  routing the primary pipeline data stream to and from the end user.
  """
  
  def setUp(self):
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Create a PipelineDataFactory with a mock session coordinator and build the test resources
    self.session_coordinator = MagicMock()
    protocol_factory = data.PipelineDataFactory(self.session_coordinator)
    self.protocol = protocol_factory.buildProtocol(('127.0.0.1', 0))
    self.old_connectionMade = self.protocol.connectionMade
    self.protocol.connectionMade = self._mock_connectionMade
    self.transport = proto_helpers.StringTransport()
    self.protocol.makeConnection(self.transport)

    # Disable logging for most events
    logging.disable(logging.CRITICAL)

  def test_sending_pipeline_output(self):
    """ Tests that the protocol can correctly relay pipeline output to its transport (and in turn to the pipeline user).
    """

    # Write some data to the protocol and check that it made it to the transport
    self.protocol.write_output("space stuff")
    self.assertEqual(self.transport.value(), "space stuff")

  def test_writing_pipeline_input(self):
    """ Verifies that the protocol can write user input it receives to its associated Session.
    """

    # Write some input before the protocol's session has been set (should have no effect)
    self.protocol.dataReceived("earth stuff")

    # Create a mock session
    self.protocol.session = MagicMock()

    # Simulate some user input
    self.protocol.dataReceived("earth stuff")
    self.protocol.session.write.assert_called_once_with("earth stuff")

  def test_protocol_registrations(self):
    """ This test verifies that the PipelineTelemetry.perform_registrations() callback correctly registers the 
    Protocol with the necessary resources and that it correctly handles possible errors.
    """

    # Create a mock session
    test_session = MagicMock()

    # Register with the mock session
    self.protocol.perform_registrations(test_session)
    test_session.register_data_protocol.assert_called_once_with(self.protocol)
    self.assertEqual(self.protocol.session, test_session)

    # Replace register_data_protocol with a mock version that will generate an exception
    test_session.register_data_protocol = self._mock_session_protocol_registration
    self.assertRaises(session.ProtocolAlreadyRegistered, self.protocol.perform_registrations, test_session)

  def test_initial_session_lookup_session_not_found(self):
    """ This test verifies that the data protocol correctly handles errors that may occur when setting up the connection
    such as an invalid session.
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
    """ This test verifies that the data protocol can load the requested session and perform the necessary registrations
    when the user connection is made via it's connectionMade() callback.
    """

    # Create a mock protocol and session to test with
    test_res_id = "res_id"
    test_session = MagicMock()
    self.protocol.connectionMade = self.old_connectionMade # Restore the actual connectionMade method for this test
    self.protocol.transport.getPeerCertificate = lambda : None
    self.protocol.session_coordinator.load_reservation_session = lambda res_id: test_session

    def validate_session(loaded_session):
      """ A callback that will receive the session once the simulated TLS handshake finishes.
      """

      self.assertEqual(loaded_session, test_session)
      self.assertEqual(self.protocol.session, test_session)
      test_session.register_data_protocol.assert_called_once_with(self.protocol)

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
    """ Simulates a duplicate data protocol registration on a Session by throwing the ProtocolAlreadyRegistered
    exception.

    @throw Always throws session.ProtocolAlreadyRegistered.
    """

    raise session.ProtocolAlreadyRegistered("Testing session-data protocol registration.")

  def _mock_session_lookup_failed(self, res_id):
    """ This function raises a coordinator.SessionNotFound exception and is used to test error handling.
    """

    raise coordinator.SessionNotFound("Test SessionNotFound exception.")

