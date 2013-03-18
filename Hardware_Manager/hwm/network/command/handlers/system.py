""" @package hwm.network.command.handlers.system
Contains a class that handles various system commands received by the ground station.
"""

# Import required modules
import time

class SystemCommandHandler:
  """ A command handler that responds to system commands.
  
  This class provides methods that handle various system commands. Every command method begins with "command_" and will 
  be called directly by the command parser.
  """
  
  def command_station_time(self, command):
    """ Returns the current ground station time.
    
    @note The timestamp is returned in the 'timestamp' field of the response 'result' dictionary.
    
    @param command  The Command object associated with the executing command.
    @return Returns the current time on the computer that is running the hardware manager.
    """
    
    return {'timestamp': time.time()}
