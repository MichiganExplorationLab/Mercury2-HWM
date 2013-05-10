""" @package hwm.command.command
Contains a class used to store the state of submitted ground station commands.
"""

# Import the required modules
import time, json, jsonschema
from twisted.internet import defer 

class Command:
  """ Used to represent user commands.
  
  This class is the default class used to represent commands sent to the ground station. Commands are typically passed 
  between the command parser and the appropriate command handler, which then updates the Command instance with the 
  results of the command. This default Command type represents simple dictionary based commands (which are probably 
  YAML or JSON strings in their raw forms).
  """
  
  def __init__(self, time_received, raw_command, user_id = None, kernel_mode = False):
    """ Constructs a new Command object.
    
    This method sets up a new command based on the raw command received.
    
    @param time_received   The time (UNIX timestamp) when the command was received.
    @param raw_command     The raw command that this class will represent. Can either be a dictionary or a string. If it
                           is a string, it will be passed through a series of parsers for the supported languages until
                           one of them can decode the string. The resulting (or original) dictionary will then be 
                           checked against the command schemma. Currently, only JSON strings are supported.
    @param user_id         The ID of the user executing the command.
    @param kernel_mode     Whether or not the command is to run in kernel mode (ignores permission and session checks).
    """
    
    # Set command attributes
    self.time_received = time_received
    self.command_raw = raw_command
    self.command_dict = None
    self.user_id = user_id
    self.kernel_mode = kernel_mode
    self.valid = False
    
    # Convenience attributes set after validate_command
    self.command = None
    self.destination = None
    self.parameters = {}
  
  def validate_command(self):
    """ Validates the submitted command and saves it in a usable form.
    
    This method verifies that the provided raw command dictionary conforms this Command's schema.
    
    @note Because simple YAML and JSON objects are both serialized representations of dictionaries, the JSON Draft 3
          schema validator can be used to check commands that were originally in JSON or YAML (or any other such 
          language). This default command class currently supports JSON strings and pre-converted dictionaries
          (typically the case when using the YAML configuration).
    @note This method should be called before any actions are performed on the command (i.e. right after 
          initialization).
    @note This method sets several convenience attributes of the Command class (such as the destination and command 
          id's) if the command conforms to the schema.
    
    @return Returns a deferred that will be fired with the results of the command validation. If the command is invalid,
            a deferred is pre-fired (with a failure) and returned with information about the failure.
    """
    
    # Check if the raw command was an unparsed string
    if isinstance(self.command_raw, basestring):
      try:
        self.command_dict = json.loads(self.command_raw)
      except ValueError:
        # Error parsing the command JSON
        return defer.fail(CommandMalformed("The submitted command was malformed and couldn't be parsed as a JSON "+
                                           "string."))
    elif not isinstance(self.command_raw, dict):
      # Not a dictionary or a string
      return defer.fail(CommandMalformed("An invalid command type was detected by the command validator."))
    else:
      self.command_dict = self.command_raw
    
    # Define the command schema
    command_schema = {
      "type": "object",
      "$schema": "http://json-schema.org/draft-03/schema",
      "required": True,
      "additionalProperties": False,
      "properties": {
        "command": {
          "type": "string",
          "id": "command",
          "required": True
        },
        "destination": {
          "type": "string",
          "id": "destination",
          "required": True
        },
        "parameters": {
          "type": "object",
          "additionalProperties": True,
          "required": False
        }
      }
    }
    
    # Validate the command schema
    command_validator = jsonschema.Draft3Validator(command_schema)
    try:
      command_validator.validate(self.command_dict)
      self.valid = True
    except jsonschema.ValidationError:
      # Invalid command schema
      return defer.fail(CommandInvalidSchema("The submitted command did not conform to the command schema for command "+
                        "type: "+self.__class__.__name__))
    
    # Populate some attributes to make the command easier to work with
    self._populate_command_attributes()
    
    return defer.succeed(True)
  
  def build_command_response(self, success, command_results = {}):
    """ Constructs a dictionary to encapsulate the command results.
    
    This method builds a dictionary containing the command's response. Whatever module created the command in the first
    place will be responsible for converting it into the format it needs. For example, the CommandResource class will 
    likely convert the results into a JSON string.
    
    @param success          Whether or not the command was successful (True or False).
    @param command_results  A dictionary containing the results of the command.
    @return Returns a dictionary containing the command's results.
    """
    
    response_info = {}
    command_response = {}
    
    # Construct the command response
    command_response['received_at'] = self.time_received
    command_response['completed_at'] = int(time.time())
    command_response['status'] = 'okay' if success else 'error'
    if self.destination:
      command_response['destination'] = self.destination
    command_response['result'] = command_results
    
    # Store the command response (what will actually be sent back to the user)
    response_info['response'] = command_response
    
    return response_info
  
  def _populate_command_attributes(self):
    """ This method populates the class's attributes using the command dictionary.
    
    This method copies some information from the command dictionary into class attributes for programmer convenience. 
    It should be called after the command's schema has been validated.
    
    @return Returns True on success or False if the command is invalid (i.e. it hasn't been validated yet or is actually
            invalid).
    """
    
    if self.valid or self.command_dict == None:
      self.command = self.command_dict['command']
      self.destination = self.command_dict['destination']
      self.parameters = self.command_dict['parameters'] if ('parameters' in self.command_dict) else None
      
      return True
    else:
      return False

# Create some exceptions for the Command class
class CommandNotFound(Exception):
  pass
class CommandInvalidSchema(Exception):
  pass
class CommandMalformed(Exception):
  pass
class CommandError(Exception):
  """ A general purpose exception thrown in the event that a command fails. It allows the command handler to embed
  additional metadata with the failure in the form of a dictionary passed to the exception."""
  
  def __init__(self, schedule_error_message, error_data = None):
    """ Sets up the command error.
    
    @param command_error_message  A string summarizing the failure.
    @param error_data             A simple dictionary containing additional fields to be passed with the error response.
    """
    
    self.message = schedule_error_message
    self.error_parameters = error_data
  
  def __str__(self):
    return self.message
