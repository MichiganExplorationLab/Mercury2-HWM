# Import required modules
import logging
from mock import MagicMock
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from twisted.test import proto_helpers
from hwm.network.protocols import data

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
    """ This test verifies that the Pipeline._protocol_registrations() callback correctly registers the Protocol with 
    the necessary resources. This method is normally called right after the protocol's session has been sent.
    """

    # Call the protocol registration callback before a session has been set (should have no effect)
    self.protocol._perform_registrations()

    # Create a mock session
    self.protocol.session = MagicMock()

    # Manually run the protocol registration callback a few times (make sure it's handling exceptions)
    self.protocol._perform_registrations()
    self.protocol.session.register_data_protocol.assert_called_once_with(self.protocol)
    self.protocol._perform_registrations()
    self.assertEqual(self.protocol.session.register_data_protocol.call_count, 2)

  def _mock_connectionMade(self):
    """ A mock version of the PipelineData Protocol that does not call the AuthUtilities._wait_for_session mixin. This
    is required because the proto_helpers.StringTransport() transport we're testing with doesn't support SSL. In
    addition, the callLater() call in _wait_for_session() would make test cleanup more difficult.
    """

    return

