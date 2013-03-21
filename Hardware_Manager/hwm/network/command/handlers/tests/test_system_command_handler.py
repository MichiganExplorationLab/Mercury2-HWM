# Import required modules
import logging, time, json
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from twisted.test import proto_helpers
from hwm.core.configuration import *
from hwm.network.command import parser, command, connection
from hwm.network.command.handlers import system as command_handler

class TestSystemCommandHandler(unittest.TestCase):
  """ This test suite is responsible for testing the functionality of the system command handler (handles general system
  wide commands). Typically commands will be simulated by either invoking the parser or the command Resource. However,
  some commands may be tested by directly accessing the command functions in the handler.
  """
  
  def setUp(self):
    # Set a local reference to Configuration (how other modules should typically access Config)
    self.config = Configuration
    self.config.verbose_startup = False
    
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
    # Initialize the command parser with the system command handler
    self.command_parser = parser.CommandParser(command_handler.SystemCommandHandler())
  
  def tearDown(self):
    # Reset the recorded configuration values
    self.config.options = {}
    self.config.user_options = {}
    
    # Reset the object references
    self.config = None
    self.command_parser = None
  
  def test_station_time(self):
    """ This test verifies that the station_time command works as intended.
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_results):
      json_response = json.loads(command_results['response'])
      self.assertEqual(json_response['status'], 'okay', 'The parser did not return a successful response.')
      self.assertTrue('timestamp' in json_response['result'], 'The response did not contain a timestamp field.')
    
    # Send a time request to the parser
    test_deferred = self.command_parser.parse_command("{\"command\": \"station_time\"}")
    test_deferred.addCallback(parsing_complete)
    
    return test_deferred
