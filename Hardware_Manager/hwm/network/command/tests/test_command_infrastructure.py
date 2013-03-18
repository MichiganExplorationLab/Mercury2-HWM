# To Test:
# - Sending command with invalid JSON
# - Sending command with invalid schema
# - Sending command with invalid device ID
# - Sending valid command schema with unrecognized command
# - Sending valid command schema with valid command (put actual command test code in test suite for command handler)
# - Test callbacks
# - Test _command_error for both normal exceptions and CommandError
# ? Test unhandled error (i.e. errback fired in connection from deferred returned from parse_command)

# Import required modules
import logging
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted_web_test_utils import DummySite
from hwm.core.configuration import *
from hwm.network.command import parser as command_parser_system, connection as command_connection
from hwm.network.command.handlers import system as command_handler_system

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
  
    # Initialize the command parser
    command_parser = command_parser_system.CommandParser(None)
  
    # Create a new Site factory
    self.command_factory_test = DummySite(command_connection.CommandResource(command_parser))
  
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

