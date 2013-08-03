""" @package hwm.command.handlers.system
Contains a class that handles various system commands received by the ground station.
"""

# Import required modules
import time
import hwm.command.metadata
from hwm.command import command
from hwm.command.handlers import handler

class SystemCommandHandler(handler.CommandHandler):
  """ A command handler that responds to system commands.
  
  This class provides methods that handle various system level commands.
  """
  
  def command_station_time(self, active_command):
    """ Returns the current ground station time.
    
    @note The timestamp is returned in the 'timestamp' field of the response 'result' dictionary.
    
    @param active_command  The Command object associated with the executing command. Contains the command parameters.
    @return Returns the current time on the computer that is running the hardware manager.
    """
    
    return {'timestamp': int(time.time())}
  
  def settings_station_time(self):
    """ Returns a dictionary containing meta-data about the station_time command.
    
    @return Returns a standard dictionary containing meta-data about the command.
    """
    
    # The station_command does not take any parameters
    command_parameters = [{}]
    
    return build_metadata_dict(command_parameters, 'station_time', self.name, requires_active_session = False,
                               dangerous = False)
  
  def command_test_error(self, active_command):
    """ Generates a simple command error for testing purposes.
    
    @throw Throws CommandError for testing.
    
    @param active_command  The command object associated with the executing command.
    """
    
    # raise the exception.
    raise command.CommandError("Command Error Test.", {"submitted_command": active_command.command})
