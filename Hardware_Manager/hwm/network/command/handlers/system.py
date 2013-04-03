""" @package hwm.network.command.handlers.system
Contains a class that handles various system commands received by the ground station.
"""

# Import required modules
import time
import hwm.network.command.metadata

class SystemCommandHandler:
  """ A command handler that responds to system commands.
  
  This class provides methods that handle various system commands. Every command method begins with "command_" and will 
  be called directly by the command parser. Functions that start with "settings_" return a dictionary containing 
  meta-data about the command such as the parameters it accepts. The user interface uses this information to build an 
  appropriate form for the command. If a command does not define a "settings_" method, it will not be included in user 
  interface forms (if it's a device command).
  
  For system commands that require an active session, the individual commands must perform any necessary validations on 
  the session. For device commands that require an active session, the command parser will ensure the command only gets
  called if the user is using a pipeline that contains that hardware device.
  
  Non-device command handler classes must start with the capitalized module name and end with "CommandHandler". For
  example, "SystemCommandHandler" in the "system" module. This is required for the command addressing system to work.
  
  @note The rationale behind defining the command meta-data at this level is so that command handlers (system or device)
        can be developed and installed without requiring any changes to the user interface (unless you want custom 
        forms). 
  """
  
  def __init__(self):
    """ Sets up the system command handler.
    """
    
    # Define the command handler's attributes
    self.name = "system"
  
  def command_station_time(self, command, active_session):
    """ Returns the current ground station time.
    
    @note The timestamp is returned in the 'timestamp' field of the response 'result' dictionary.
    
    @param command         The Command object associated with the executing command. Contains the command parameters.
    @param active_session  The active Session object for the user that submitted the request, if any (None if the user
                           doesn't have an active session).
    @return Returns the current time on the computer that is running the hardware manager.
    """
    
    return {'timestamp': time.time()}
  
  def settings_station_time(self):
    """ Returns a dictionary containing meta-data about the station_time command.
    
    @return Returns a standard dictionary containing meta-data about the command.
    """
    
    # The station_command does not take any parameters
    command_parameters = [{}]
    
    return build_metadata_dict(command_parameters, 'station_time', False, self.name, None)
