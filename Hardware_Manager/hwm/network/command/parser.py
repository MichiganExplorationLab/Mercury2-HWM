""" @package hwm.network.command.parser
Parses system and hardware commands and passes them to the appropriate command handler.

This module contains a class that validates, parses, and delegates ground station commands as they're received.
"""

# Import required modules
import json, time
from twisted.internet import defer, threads
from jsonschema import Draft3Validator

class CommandParser:
  """ Processes all commands received by the hardware manager.
  
  This class parses and performs validations on received commands, delegating them to the appropriate handler when
  appropriate.
  """
  
  def __init__(self, system_command_handler):
    """ Sets up the command parser instance.
    
    @param system_command_handler  A reference to the command handler that is responsible for handling system commands 
                                   (i.e. commands not addressed to a specific device).
    """
    
    # Set the class attributes
    self.system_handler = system_command_handler

  def parse_command(self, raw_command, request = None):
    """ Processes all commands received by the ground station.
    
    When a raw JSON command is passed to this function, it performs the following operations:
    * Validates command schema
    * Verifies that the command is valid (exists)
    * Checks that the user can execute the command
    * Executes the command in a new thread
    * Returns a deferred that will be fired with the results of the command
    
    @note In the event of an error with the command (e.g. invalid json or permission error), the error will be logged
          and an error response will be returned.
    @note Even if the command generates an error response, the resulting deferred's callback chain will still be fired 
          (not the errback chain). However, if an unhandled error occurs the errback chain will still be fired.
    
    @param raw_command  A raw JSON string containing metadata about the command.
    @param request      The request object associated with the command, if any.
    @return Returns the results of the command (in JSON) using a deferred. May be the output of the command or an error 
            message.
    """
    
    time_command_received = time.time()
    
    # Convert the JSON string
    try:
      command_json = json.loads(raw_command)
    except ValueError:
      logging.error("A received command contained invalid JSON and could not be parsed.")
      command_deferred = self._command_error(request, time_command_received, "The submitted command did not contain a valid JSON string.")
      
      return command_deferred
    
    # Validate the command schema
    if not self._valid_command_schema(raw_command):
      logging.error("A received command did not conform to the command schema.")
      command_deferred = self._command_error(request, time_command_received, "The submitted command did not conform to the defined command schema.")
      
      return command_deferred
    
    # Determine command type
    if 'device_id' in command_json:
      # Load the corresponding device command handler
      print 'LOAD DEVICE HANDLER'
    else:
      # Load the system command handler
      command_handler = self.system_handler
    
    # Verify that the command exists
    if not hasattr(command_handler, 'command_'+command_json['command']):
      if 'device_id' in command_json:
        handler_string = "'"+command_json['device_id']+"' device"
      else:
        handler_string = "system"
      
      logging.error("A received command could not be located in the "+handler_string+" command handler: "+command_json['command'])
      command_deferred = self._command_error(request, time_command_received, "The submitted command could not be located in the "+handler_string+" command handler: "+command_json['command'])
    
    # Check the user permissions
    
    # Execute the command in a new thread
    command_deferred = threads.deferToThread(getattr(command_handler, 'command_'+command_json['command']))
    command_deferred.addCallback(self._command_complete)
    
    return command_deferred
  
  def _command_complete(self, command_results){
    """ A callback that packages the results of a command.
    
    This callback packages up the results of a command and builds the command response, which it then passes down the
    call back chain.
    
    @param command_results  A dictionary containing the results of the executed command.
    """
    
    # Build the command response
    command_response = self._build_command_response(True, time_received, command_results
  }
  
  def _command_error(self, request, time_received, error_message):
    """ Generates a JSON error message and returns it using a deferred.
    
    @param request        The request associated with the command.
    @param time_received  A unix timestamp indicating the time the command was received.
    @param error_message  A string containing information about the error.
    @return Returns a deferred that has been triggered with the JSON error string.
    """
    
    # Set the error message
    error_results = {
      "error_message": error_message
    }
    
    # Build the response
    error_response = self._build_command_response(False, time_received, error_results, None, request)
    
    # Return the fired deferred
    return defer.succeed(error_response)
  
  def _build_command_response(self, success, time_received, command_results = {}, device_id = None, request = None):
    """ Constructs a dictionary to encapsulate command results.
    
    This method builds a dictionary containing the command JSON response as well as the associated request object, if 
    any. The returned dictionary will probably be fed into a deferred which will be used by the command Resource.
    
    @param success          Whether or not the command was successful (True or False).
    @param time_received    The time (UNIX timestamp) when the command was first received (passed to the parser)
    @param command_results  A dictionary containing the results of the command.
    @param device_id        The ID of the device the command was addressed to, if any.
    @param request          The request associated with the command, if any.
    """
    
    # Set the request reference
    command_response['request'] = request
    
    # Construct the command response
    json_response['time_received'] = time_received
    json_response['time_completed'] = time.time()
    
    if success:
      json_response['status'] = 'okay'
    else:
      json_response['status'] = 'error'
    
    if device_id:
      json_response['device_id'] = device_id
    
    json_response['result'] = command_results
    
    # Convert the response JSON 
    command_response['response'] = json.dumps(json_response)
    
    return command_response
  
  def _valid_command_schema(self, raw_command):
    """ Validates the provided command schema.
    
    This method verifies that the submitted schema conforms to the command schema.
    
    @param raw_command  The raw JSON string for the command.
    @return Returns True if the provided command schema is valid and False otherwise.
    """
    
    # Define the command schema
    command_schema = {
      "type": "object",
      "$schema": "http://json-schema.org/draft-03/schema",
      "required": True,
      "properties": {
        "command": {
          "type": "string",
          "id": "command"
        },
        "device_id": {
          "type": "string",
          "id": "device_id",
          "required": False
        },
        "parameters": {
          "type": "object",
          "additionalProperties": True,
          "required": False
        }
      }
    }
    
    # Validate the JSON schema
    command_validator = Draft3Validator(command_schema)
    try:
      command_validator.validate(raw_command)
    except:
      # Invalid command schema
      return False
    
    return True
