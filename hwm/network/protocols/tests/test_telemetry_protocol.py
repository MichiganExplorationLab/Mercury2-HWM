# Import required modules
import logging, json
from mock import MagicMock
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from twisted.test import proto_helpers
from hwm.network.protocols import telemetry

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
      "telemetry": "just some telemetry"
    }
    self.protocol.write_telemetry(telem_point['source'], telem_point['stream'],
                                  telem_point['generated_at'], telem_point['telemetry'])
    received_dictionary = json.loads(self.transport.value())
    self.assertTrue(set(telem_point) == set(received_dictionary))
    self.transport.clear()

    # Now try sending a telemetry data point that contains some extra headers
    telem_point = {
      "source": "test_source",
      "stream": "test_stream",
      "generated_at": 42,
      "telemetry": "just some telemetry",
      "test_header": True,
      "test_header_2": "just some metadata"
    }
    self.protocol.write_telemetry(telem_point['source'], telem_point['stream'],
                                  telem_point['generated_at'], telem_point['telemetry'],
                                  test_header=telem_point['test_header'], test_header_2=telem_point['test_header_2'])
    received_dictionary = json.loads(self.transport.value())
    self.assertTrue(set(received_dictionary) == set(telem_point))

  def test_sending_pipeline_telemetry_binary(self):
    """ Tests that the protocol can send binary telemetry data over the network. By setting the "binary" attribute to 
    true when writing telemetry to the session, pipelines and devices can send binary data like images and audio clips 
    to the pipeline user.
    """ 

    pass

  def _mock_connectionMade(self):
    """ A mock version of the PipelineData Protocol that does not call the AuthUtilities._wait_for_session mixin. This
    is required because the proto_helpers.StringTransport() transport we're testing with doesn't support SSL. In
    addition, the callLater() call in _wait_for_session() would make test cleanup more difficult.
    """

    return
