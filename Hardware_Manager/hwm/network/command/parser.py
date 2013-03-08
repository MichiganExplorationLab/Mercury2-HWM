""" @package hwm.network.command.parser
Parses system and hardware commands and passes them to the appropriate command handler.

This module contains a class that validates, parses, and delegates ground station commands as they're received.
"""

# Import required modules

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
    
    @param raw_command  A raw JSON string containing metadata about the command.
    @return Returns the results of the command (in JSON). May be the output of the command or an error message.
    """
    
    # Validate the command schema
    
    # Determine command type
    
    # Verify that the command exists
    
    # Check the user permissions
  
  
