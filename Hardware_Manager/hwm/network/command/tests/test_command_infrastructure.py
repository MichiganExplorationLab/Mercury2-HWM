# To Test:
# - Sending command with invalid schema
# - Sending command with invalid device ID
# - Sending valid command schema with unrecognized command
# - Sending valid command schema with valid commands (add tests per command)

# Import required modules
import logging
from twisted.trial import unittest
from twisted.test import proto_helpers
from hwm.core.configuration import *
from hwm.network.command.connection import CommandFactory
from pkg_resources import Requirement, resource_filename

class TestCommandInfrastructure(unittest.TestCase):
  """ This test suite tests the base command receiving and processing functionality of the hardware manager. These tests
  do not test any driver-specific commands (each driver should contain its own test case).
  """
  
  def setUp(self):
    # Set a local reference to Configuration (how other modules should typically access Config)
    self.config = Configuration
    self.config.verbose_startup = False
    
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
    
    # Construct an instance of the protocol
    command_factory = CommandFactory()
    self.protocol = command_factory.buildProtocol(('127.0.0.1', 0))
    self.transport = proto_helpers.StringTransport()
    self.protocol.makeConnection(self.transport)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self.config.options = {}
    self.config.user_options = {}
    
    # Reset the configuration reference
    self.config = None
  
  def test_invalid_schema(self):
    """ Verifies that the CommandConnection protocol returns a schema error when an invalid schema is received.
    """
    
    # Send an invalid schema over the transport
    self.protocol.rawDataReceived('TEST DATA RECEIVED')
    self.assertEqual(self.transport.value(), 'test')

