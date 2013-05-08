""" @package hwm.network.command.command
Contains a class used to store the state of submitted ground station commands.
"""

# Import the required modules
import time, json, jsonschema
from twisted.internet import defer 

class Command:
  """ Used to represent user commands.
  
  This class is used to represent commands sent to the ground station. Commands are typically passed between the command
  parser and the appropriate command handler, which then updates the Command instance with the results of the command.
  This default Command type represents JSON formatted commands.
  """
  
  def __init__(self, time_received, raw_command, user_id, active_session = None):
    """ Constructs a new Command object.
    
    This method sets up a new command based on the raw command received.
    
    @param time_received   The time (UNIX timestamp) when the command was received.
    @param raw_command     A JSON string representing the command.
    @param user_id         The ID of the user executing the command.
    @param active_session  A reference to the active Session for the connected user, if any.
    """
    
    # Set command attributes
    self.time_received = time_received
    self.command_raw = raw_command
    self.command_json = None
    self.user_id = user_id
    self.valid = False
    self.session = active_session
    
    # Convenience attributes set after validate_command
    self.command = None
    self.destination = None
    self.parameters = {}
  
  def validate_command(self):
    """ Validates the submitted command and saves it in a usable form.
    
    This method verifies that the provided raw command string conforms this Command's schema. In addition, it also
    converts and saves it into something more useful than a string (a JSON object).
    
    @note This method should be called before any actions are performed on the command (i.e. right after initialization).
    @note This method sets several convenience attributes of the Command class (such as the destination and command 
          id's) if the command conforms to the schema.
    
    @return Returns a deferred that will be fired with the results of the command validation. If the command is invalid,
            a deferred is pre-fired (with a failure) and returned with information about the failure.
    """
    
    # Try to convert the command string to JSON
    try:
      self.command_json = json.loads(self.command_raw)
    except ValueError:
      return defer.fail(CommandMalformed("The submitted command contained a malformed JSON string."))
    
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
    
    # Validate the JSON schema
    command_validator = jsonschema.Draft3Validator(command_schema)
    try:
      command_validator.validate(self.command_json)
      self.valid = True
    except jsonschema.ValidationError:
      # Invalid command schema
      return defer.fail(CommandInvalidSchema("The submitted command did not conform to the command schema for command type: "+self.__class__.__name__))
    
    # Populate some attributes to make the command easier to work with
    self._populate_command_attributes()
    
    return defer.succeed(True)
  
  def build_command_response(self, success, command_results = {}):
    """ Constructs a dictionary to encapsulate the command results.
    
    This method builds a dictionary containing the command's JSON response. CommandResource will use the returned 
    dictionary to send the response to the user.
    
    @param success          Whether or not the command was successful (True or False).
    @param command_results  A dictionary containing the results of the command.
    @return Returns a dictionary containing the command's results.
    """
    
    command_response = {}
    json_response = {}
    
    # Construct the command response
    json_response['received_at'] = self.time_received
    json_response['completed_at'] = time.time()
    
    if success:
      json_response['status'] = 'okay'
    else:
      json_response['status'] = 'error'
    
    if self.destination:
      json_response['destination'] = self.destination
    
    json_response['result'] = command_results
    
    # Convert the response JSON 
    command_response['response'] = json.dumps(json_response)
    
    return command_response
  
  def _populate_command_attributes(self):
    """ This method populates the class's attributes using the command JSON.
    
    This method copies some information from the command JSON object into class attributes for programmer convenience. 
    It should be called after the command's schema has been validated.
    
    @note If this method is called before the command has been validated, it will return False.
    
    @return Returns True on success or False otherwise.
    """
    
    if self.valid and (self.command_json is not None):
      self.command = self.command_json['command']
      self.destination = self.command_json['destination']
      self.parameters = self.command_json['parameters'] if ('parameters' in self.command_json) else None
      
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
