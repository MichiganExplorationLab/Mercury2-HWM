# Import required modules
import logging, time, json
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from twisted.test import proto_helpers
from hwm.core.configuration import *
from hwm.command import parser, command, connection, metadata
from hwm.command.handlers import system as command_handler
from hwm.network.security import permissions

class TestCommandInfrastructure(unittest.TestCase):
  """ This test suite tests the functionality of the command parser (CommandParser), default Command class, and command 
  Resource individually and holistically. The functionality of individual commands (including system commands) is tested
  in the test suite for the containing command handler.
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
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json', 3600)
    self.command_parser = parser.CommandParser([command_handler.SystemCommandHandler('system')], permission_manager)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self.config.options = {}
    self.config.user_options = {}
    
    # Reset the object references
    self.config = None
    self.command_parser = None
  
  def test_metadata_errors(self):
    """ Test that the command metadata generation function correctly returns errors when appropriate. If there are some
    subtle errors that don't get detected by the build_metadata_dict function, they will be handled when the command 
    is processed.
    """
    
    # Try to create a metadata structure without a location
    self.assertRaises(metadata.InvalidCommandAddress, metadata.build_metadata_dict, [{}], 'test_command', None, False)
    
    # Don't specify a command ID
    self.assertRaises(metadata.InvalidCommandMetadata, metadata.build_metadata_dict, [{}], '', 'system', False)
    
    # Include some parameters with invalid types
    test_parameters = [
      {'title': 'test_argument',
       'type': 'string',
       'required:': True,
       'maxlength': 10},
      {'title': 'test_argument2',
       'type': 'invalid_type'}
    ]
    self.assertRaises(metadata.InvalidCommandMetadata, metadata.build_metadata_dict, test_parameters, 'test_command', 'system', False)
    
    # Specify a parameter without a title (required to represent the parameter in the UI)
    test_parameters = [
      {'title': 'test_argument',
       'type': 'string',
       'required:': True,
       'maxlength': 10},
      {'type': 'boolean'}
    ]
    self.assertRaises(metadata.InvalidCommandMetadata, metadata.build_metadata_dict, test_parameters, 'test_command', 'system', False)
    
    # Specify a select with no options
    test_parameters = [
      {'title': 'test_argument',
       'type': 'select',
       'required:': False,
       'options': []}
    ]
    self.assertRaises(metadata.InvalidCommandMetadata, metadata.build_metadata_dict, test_parameters, 'test_command', 'system', False)
    
    # Specify a select with a malformed option
    test_parameters = [
      {'title': 'test_argument',
       'type': 'select',
       'required:': False,
       'options': [
         ['option_title', 'value'],
         ['option_title2', 'value1', 'value2']
       ]}
    ]
    self.assertRaises(metadata.InvalidCommandMetadata, metadata.build_metadata_dict, test_parameters, 'test_command', 'system', False)
  
  def test_metadata_types(self):
    """ Tests that the command metadata generation function accepts the types that it should.
    """
    
    # Assemble some parameters that use every valid type with some random restrictors thrown in
    test_parameters = [
      {'title': 'test_string',
       'type': 'string',
       'required': True,
       'minlength': 5,
       'maxlength': 25},
      {'title': 'test_number',
       'type': 'number',
       'integer': True},
      {'title': 'test_boolean',
       'type': 'boolean',
       'description': 'Just a test boolean, nothing to see here citizen.',
       'required': False},
      {'title': 'test_select',
       'type': 'select',
       'multiselect': True,
       'options': [
         ['First Option', 'option_a'],
         ['Second Option', 'option_b']
       ]}
    ]
    
    metadata.build_metadata_dict(test_parameters, 'test_command', 'system', False)
  
  def test_parser_unrecognized_command(self):
    """ This test ensures that the command parser correctly rejects unrecognized commands. In addition, it verifies the 
    functionality of the optional CommandError exception which allows additional meta-data to be embedded with the 
    error.
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_failure):
      response_dict = command_failure.value.results['response']
      
      self.assertEqual(response_dict['status'], 'error', 'The parser did not return an error response.')
      self.assertEqual(response_dict['result']['invalid_command'], 'nonexistent_command', 'The error response returned by the parser was incorrect (did not contain \'invalid_command\' field).')
    
    # Send an unrecognized command the to parser
    test_deferred = self.command_parser.parse_command("{\"command\":\"nonexistent_command\",\"destination\":\"system\",\"parameters\":{\"test_parameter\":5}}", user_id='4')
    test_deferred.addErrback(parsing_complete)
    
    return test_deferred
  
  def test_parser_malformed(self):
    """ This test verifies that CommandParser correctly returns the correct error response when a malformed command is 
    submitted to it.
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_failure):
      response_dict = command_failure.value.results['response']
      
      self.assertEqual(response_dict['status'], 'error', 'The parser did not return an error response.')
      self.assertNotEqual(response_dict['result']['error_message'].find('malformed'), -1, 'The parser did not return the correct error response (response did not contain \'malformed\').')
    
    # Send a malformed command the to parser
    test_deferred = self.command_parser.parse_command("{\"invalid_json\":true,invalid_element}", user_id='4')
    test_deferred.addErrback(parsing_complete)
    
    return test_deferred
  
  def test_parser_invalid_schema(self):
    """ This test verifies that CommandParser correctly returns an error when an invalid command is submitted to it (i.e.
    a command that doesn't conform to the schema).
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_failure):
      response_dict = command_failure.value.results['response']
      
      self.assertEqual(response_dict['status'], 'error')
    
    # Parse an invalid command the to parser (doesn't contain a destination)
    test_deferred = self.command_parser.parse_command("{\"command\":\"test_command\",\"parameters\":{\"test_parameter\":5}}", user_id='4')
    test_deferred.addErrback(parsing_complete)
    
    return test_deferred
  
  def test_parser_no_permissions(self):
    """ This test verifies that CommandParser correctly generates an error when a user tries to execute a command 
    that they don't have permission to execute.
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_failure):
      response_dict = command_failure.value.results['response']
      
      self.assertEqual(response_dict['status'], 'error', 'The parser did not return an error response.')
      self.assertEqual(response_dict['result']['restricted_command'], 'station_time', "The returned error response was incorrect (didn't include the 'restricted_command' field).")
    
    # Send a command that the user can't execute
    test_deferred = self.command_parser.parse_command("{\"command\":\"station_time\",\"destination\":\"system\"}", user_id='5')
    test_deferred.addErrback(parsing_complete)
    
    return test_deferred
  
  def test_parser_successful_command_dict(self):
    """ This test verifies that the command parser allows a user to execute a command (that they have permission to)
    initially supplied as a dictionary.
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_results):
      response_dict = command_results['response']
      self.assertEqual(response_dict['status'], 'okay', 'The parser did not return a successful response.')
      self.assertTrue('timestamp' in response_dict['result'], 'The response did not contain a timestamp field.')
    
    # Send a time request command to the parser
    test_command = {
      'command': "station_time",
      'destination': "system"
    }
    test_deferred = self.command_parser.parse_command(test_command, user_id="4")
    test_deferred.addCallback(parsing_complete)
    
    return test_deferred
  
  def test_parser_successful_command(self):
    """ This test verifies that the command parser allows a user to execute a command (that they have permission to) and
    returns the correct response.
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_results):
      response_dict = command_results['response']
      self.assertEqual(response_dict['status'], 'okay', 'The parser did not return a successful response.')
      self.assertTrue('timestamp' in response_dict['result'], 'The response did not contain a timestamp field.')
    
    # Send a time request command to the parser
    test_deferred = self.command_parser.parse_command("{\"command\": \"station_time\",\"destination\":\"system\"}", user_id="4")
    test_deferred.addCallback(parsing_complete)
    
    return test_deferred
  
  def test_parser_successful_kernel_command(self):
    """ This test verifies that the command parser can correctly execute a command in kernal mode. That is, a command
    that is not associated with any particular user and immune from session and permission requirements.
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_results):
      response_dict = command_results['response']
      
      self.assertEqual(response_dict['status'], 'okay', 'The parser did not return a successful response.')
      self.assertTrue('timestamp' in response_dict['result'], 'The response did not contain a timestamp field.')
    
    # Send a time request command to the parser
    test_deferred = self.command_parser.parse_command("{\"command\": \"station_time\",\"destination\":\"system\"}", kernel_mode=True)
    test_deferred.addCallback(parsing_complete)
    
    return test_deferred

  def test_parser_unrecognized_kernel_command(self):
    """ Test that kernel mode commands correctly generate error responses for invalid commands. In this case, an
    unrecognized command will be used to trigger the error.
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_failure):
      response_dict = command_failure.value.results['response']
      
      self.assertEqual(response_dict['status'], 'error', 'The parser did not return an error response.')
      self.assertEqual(response_dict['result']['invalid_command'], 'nonexistent_command', 'The error response returned by the parser was incorrect (did not contain \'invalid_command\' field).')
    
    # Send an unrecognized command the to parser
    test_deferred = self.command_parser.parse_command("{\"command\":\"nonexistent_command\",\"destination\":\"system\",\"parameters\":{\"test_parameter\":5}}", kernel_mode=True)
    test_deferred.addErrback(parsing_complete)
    
    return test_deferred

  def test_parser_failed_command(self):
    """ This test verifies that the command parser correctly returns an error response when a command fails (i.e. raises
    an exception).
    """
    
    # Define a callback to test the parser results
    def parsing_complete(command_failure):
      response_dict = command_failure.value.results['response']
      
      self.assertEqual(response_dict['status'], 'error', 'The parser did not return an error response.')
      self.assertTrue('submitted_command' in response_dict['result'], 'The response did not contain the expected test error field.')
      self.assertEqual(response_dict['result']['submitted_command'], 'test_error', 'The response did not contain the expected test error field value.')
    
    # Send a time request command to the parser
    test_deferred = self.command_parser.parse_command("{\"command\": \"test_error\",\"destination\":\"system\"}", user_id="4")
    test_deferred.addErrback(parsing_complete)
    
    return test_deferred
  
  def test_command_malformed(self):
    """ Verifies that the Command class validator correctly rejects malformed commands (i.e. commands that aren't valid
    JSON.
    """
    
    # Create a new malformed command
    test_command = command.Command(time.time(), "{\"invalid_json\":true,invalid_element}", user_id='4')
    
    test_deferred = test_command.validate_command()
    
    return self.assertFailure(test_deferred, command.CommandMalformed)
  
  def test_command_invalid_schema(self):
    """ Verifies that the Command class validator correctly rejects a command that does not conform to the JSON schema.
    """
    
    # Create a new invalid command
    test_command = command.Command(time.time(), "{\"message\": \"This schema is invalid\"}", user_id='4')
    
    test_deferred = test_command.validate_command()
    
    return self.assertFailure(test_deferred, command.CommandInvalidSchema)
  
  def test_command_missing_destination(self):
    """ Verifies that the Command class validator correctly rejects a command that does not provide a destination.
    """
    
    # Create a new command without a destination
    test_command = command.Command(time.time(), "{\"command\":\"test_command\",\"parameters\":{\"test_parameter\":5}}", user_id='4')
    
    test_deferred = test_command.validate_command()
    
    return self.assertFailure(test_deferred, command.CommandInvalidSchema)
  
  def test_command_valid_schema(self):
    """ This test verifies that the Command class correctly parses a valid schema and updates the Command attributes. In
    addition, it verifies that the build_command_response method works as intended. 
    """
    
    # Create a valid command
    test_command = command.Command(time.time(), "{\"command\":\"test_command\",\"destination\":\"system\",\"parameters\":{\"test_parameter\":5}}", user_id='4')
    
    # Define a callback to verify the Command after validation is complete
    def validation_complete(validation_results):
      # Verify that the command attributes have correctly been saved in the Command attributes
      attribute_error_message = "One of the Command convenience attributes was incorrect."
      self.assertEqual(test_command.command, "test_command", attribute_error_message)
      self.assertEqual(test_command.destination, "system", attribute_error_message)
      self.assertEqual(test_command.parameters['test_parameter'], 5, attribute_error_message)
      
      # Build and test the command response
      response_error_message = "The generated command response was invalid."
      test_command_response = test_command.build_command_response(True, {"test_result": 10})
      
      response_dict = test_command_response['response']
      self.assertEqual(response_dict['status'], 'okay', response_error_message)
      self.assertEqual(response_dict['destination'], 'system', response_error_message)
      self.assertEqual(response_dict['result']['test_result'], 10, response_error_message)
    
    test_deferred = test_command.validate_command()
    test_deferred.addCallback(validation_complete)
    
    return test_deferred
