""" This module contains a mock command handler that is used for testing purposes.
"""

# Import required modules
from hwm.command.metadata import *
from hwm.command import command
from hwm.command.handlers import handler

class TestCommandHandler(handler.CommandHandler):
  """ A test command handler containing commands designed to test the command system.
  """
  
  def command_generate_error(self, active_command):
    """ Generates a simple command error for testing purposes.
    
    @throw Throws CommandError for testing.
    
    @param active_command  The command object associated with the executing command.
    """
    
    # raise the exception.
    raise command.CommandError("Command Error Test.", {"submitted_command": active_command.command})

  def command_requires_session(self, active_command):
    """ This test command requires that the user have an active session.

    @throw Throws CommandError for testing.
    
    @param active_command  The command object associated with the executing command.
    """

    return {'some_results': True}

  def settings_requires_session(self):
    """ Returns a dictionary containing meta-data about the requires_session command.
    
    @return Returns a standard dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'requires_session', self.name, requires_active_session = True)