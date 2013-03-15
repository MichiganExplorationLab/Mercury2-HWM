""" @package hwm.network.command.command
Contains a class used to store the state of submitted ground station commands.
"""

class Command:
  """ Used to represent user commands.
  
  This class is used to represent commands sent to the ground station. Commands are typically passed between the command
  parser and the appropriate command handler, which then updates the Command instance with the results of the command.
  """
  
  def __init__(self, request, time_received, raw_command):
    """ Constructs a new Command object.
    
    This method sets up a new command based on the raw command received.
    
    @param request        The twisted.web.http.Request associated with the command.
    @param time_received  The time (UNIX timestamp) when the command was received.
    @param raw_command    A JSON string representing the command.
    """
    
    # Set the command attributes
    self.request = request
    self.time_received = time_received
    self.command_raw = raw_command
  
  def validate_command(self):
    """ Validates the submitted command and save it in a usable form.
    
    This method verifies that the provided raw command string conforms this Command's schema. In addition, it also
    converts and saves it into something more useful than a string.
    
    @note This method should be called before any actions are performed on the command (i.e. right after initialization).
    @note The rationale behind not using a factory to create commands is because 
    
    @throws CommandInvalidSchema  Thrown if the submitted command does not conform to this Command class's defined 
                                  schema.
    @throws CommandMalformed      Thrown if the submitted command can not be parsed into something that can be 
                                  run through the validator.
    
    @return Returns True if the command is valid (exception thrown otherwise).
    """
    
    # Try to convert the command string to JSON
    try:
      self.command_json = json.loads(raw_command)
    except ValueError:
      raise CommandMalformed
    
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
      command_validator.validate(self.command_json)
    except:
      # Invalid command schema
      raise CommandInvalidSchema
    
    return True

# Create some exceptions for the Command class
class CommandInvalidSchema(Exception):
  pass
class CommandMalformed(Exception):
  pass
