""" @package hwm.network.command.parser
Parses system and hardware commands and passes them to the appropriate command handler.

This module contains a class that validates, parses, and delegates ground station commands as they're received.
"""

# Import required modules
import json, time
from twisted.internet import defer
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

  def parse_command(self, raw_command):
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
    @return Returns the results of the command (in JSON) using a deferred. May be the output of the command or an error 
            message.
    """
    
    time_command_received = time.time()
    
    # Convert the JSON string
    try:
      command_json = json.loads(raw_command)
    except ValueError:
      # Error parsing the command JSON
      logging.error("A received command contained invalid JSON and could not be parsed.")
      command_deferred = self._command_error(time_command_received, "The submitted command did not contain a valid JSON string.")
      
      return command_deferred
    
    # Validate the command schema
    if not self._valid_command_schema(raw_command):
      logging.error("A received command did not conform to the command schema.")
      command_deferred = self._command_error(time_command_received, "The submitted command did not conform to the defined command schema.")
      
      return command_deferred
    
    # Determine command type
    
    # Verify that the command exists
    
    # Check the user permissions
    
    # Execute the command in a new thread
    
    return command_deferred
  
  def _command_error(self, time_received, error_message):
    """ Generates a JSON error message and returns it using a deferred.
    
    @param time_received  A unix timestamp indicating the time the command was received.
    @param error_message  A string containing information about the error.
    @return Returns a deferred that has been triggered with the JSON error string.
    """
    
    # Construct the JSON error message
    json_error_response = json.dumps({
      "status": "error",
      "error_message": error_message,
      "time_received": time_received,
      "time_completed": time.time()
    })
    
    # Return the fired deferred
    return defer.succeed(json_error_response)
  
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
