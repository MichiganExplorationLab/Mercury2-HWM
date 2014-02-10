""" @package hwm.command.parser
Parses system and hardware commands and passes them to the appropriate command handler.

This module contains a class that validates, parses, and delegates ground station commands to the appropriate handler 
as they're received. Once a command has been executed, it returns the results of the command.
"""

# Import required modules
import time, logging
from twisted.internet import defer, threads
from hwm.command import command
from hwm.hardware.devices.drivers import driver
from hwm.hardware.devices import manager as device_manager
from hwm.hardware.pipelines import manager as pipeline_manager

class CommandParser:
  """ Processes all commands received by the hardware manager.
  
  This class parses and performs validations on received commands, delegating them to the appropriate command handler.
  """
  
  def __init__(self, system_command_handlers, permission_manager):
    """ Sets up the command parser instance.
    
    @param system_command_handlers  A array containing references to all of the system command handlers. If a command's 
                                    destination field references an element in this dictionary, that command handler 
                                    will be used. Otherwise, it will be delegated to a device command handler.
    @param permission_manager       A reference to the permissions manager instance that will be used to determine if a
                                    user has the permissions to execute a given command.

    @note This class requires that a SessionCoordinator instance be initialized with an instance of this class before it 
          can parse commands. It needs the session coordinator to load the user's active sessions, and the session 
          coordinator needs this class so that it can pass it to newly created sessions for their setup commands.
    @note This class requires that a PipelineManager instance be initialized with an instance of this class before it 
          can parse device commands. This is required so that it can relay device commands to the specified device.
    """
    
    # Set the class attributes
    self.system_handlers = {}
    for command_handler in system_command_handlers:
      self.system_handlers[command_handler.name] = command_handler
    self.permission_manager = permission_manager
    self.pipeline_manager = None
    self.session_coordinator = None

  def system_command_handlers(self):
    """ Provides access to the loaded system command handlers.

    @return Returns the dictionary containing references to the available system command handlers.
    """

    return self.system_handlers

  def parse_command(self, raw_command, user_id = None, kernel_mode = False):
    """ Processes all commands received by the ground station.
    
    When a raw command is passed to this function, it performs the following operations via a series of callbacks:
    * Constructs a new Command and validates it against that command's schema
    * Verifies that the indicated command exists
    * Checks that the user can execute the command
    * Executes the command in a new thread
    * Returns a deferred that will be fired with the results of the command
    
    Some of these steps may be skipped depending on the type of command. For example, kernel level commands skip the 
    permission checking phase.
    
    @note In the event of an error with the command (e.g. invalid schema or permission error), the error will be logged
          and an error response will be returned via the returned deerred's errback chain.
    @note The callback/errback chain for the deferred returned from this function will be fired with a dictionary 
          containing the results of the command. In the event of an error, these results can be accessed using the 
          returned Failure like so: Failure.value.results['response']. In the event of a success, these results can be 
          accessed via the 'response' key of the callback parameter. The calling module is responsible for converting 
          this dictionary into an appropriate format.
    
    @param raw_command  A raw command containing metadata about the command in an arbitrary format (specific Command
                        classes are responsible for parsing different formats).
    @param user_id      The user's ID for the purpose of loading command execution settings. If set, this probably came 
                        from the user's SSL certificate or reservation schedule.
    @param kernel_mode  Indicates if the command should be run in kernel mode. That is, whether permission and session
                        restrictions should be ignored. This is done, for example, when pipeline setup commands get run
                        as a new session is being setup.
    @return Returns the results of the command in a dictionary using a deferred. May be the output of the command or a
            Failure (containing details about the failure) in the event of an error.
    """
    
    # Local variables
    time_command_received = int(time.time())
    
    # Create the new command (currently there is only one command type to worry about)
    new_command = command.Command(time_command_received, raw_command, user_id=user_id, kernel_mode=kernel_mode)

    # Validate the command (format and schema)
    command_deferred = new_command.validate_command()
    
    # Add callbacks to handle validation results (_command_error added second so it can handle errors from 
    # _load_permissions() and its deferred chain)
    command_deferred.addCallback(self._load_permissions, new_command)
    command_deferred.addErrback(self._command_error, new_command)
    
    return command_deferred

  def _load_permissions(self, validation_results, valid_command):
    """ Loads the user's permissions, if required.
    
    This callback runs after the command has been validated and is responsible for loading a user's permissions to make
    sure that the user has permission to execute the command. If the command is being executed in kernel mode, then this
    step will be skipped and a pre-fired deferred will be returned to continue the execution process.
    
    @throw This callback may throw several exceptions indicating errors about the command. These exceptions will 
           automatically be picked up by the errback chain on the parent deferred.
    
    @param validation_results  The validation results. Always true (because this is a callback and not an errback).
    @param valid_command       The Command object being executed.
    @return Returns a deferred that will eventually be fired with the user's command execution permissions (or None if
            the command is being run in kernel mode).
    """
    
    # Check if the command is being run in kernel mode
    if valid_command.kernel_mode:
      # Return a pre-fired deferred
      continue_exec_deferred = defer.Deferred()
      continue_exec_deferred.addCallback(self._run_command, valid_command)
      continue_exec_deferred.callback(None)
      
      return continue_exec_deferred
    else:
      # Fetch the user's permissions
      permission_load_deferred = self.permission_manager.get_user_permissions(valid_command.user_id)
      permission_load_deferred.addCallback(self._run_command, valid_command)
      
      return permission_load_deferred
  
  def _run_command(self, user_permissions, valid_command):
    """ Executes the command after it has been validated.

    This callback sends the command to it's specified destination after it has been validated by previous callbacks. It
    will eventually return the command response via a deferred.

    @throw May throw CommandError and other exceptions indicating that the command has failed. A subsequent errback in 
           the main command deferred chain will automatically handle all command errors. 
    
    @param user_permissions  A dictionary containing the user's permissions. If the command is being running in kernel
                             mode, this will just be None.
    @param valid_command     The Command object for the currently executing command.
    @return Returns a deferred that will eventually be fired with the results of the command execution.
    """
    
    # Determine where to send the command
    device_command = False
    destination = valid_command.destination
    full_destination = valid_command.full_destination
    pipeline = valid_command.pipeline
    if destination in self.system_handlers:
      # System Command
      command_handler = self.system_handlers[destination]
    elif pipeline is not None:
      # Device Command
      device_command = True

      try:
        dest_pipeline = self.pipeline_manager.get_pipeline(pipeline)
      except pipeline_manager.PipelineNotFound as e:
        raise command.CommandError(str(e), {"command": valid_command.command, "destination": full_destination})

      try:
        dest_device = dest_pipeline.get_device(destination)
      except device_manager.DeviceNotFound as e:
        raise command.CommandError(str(e), {"command": valid_command.command, "destination": full_destination})

      try:
        command_handler = dest_device.get_command_handler()
      except driver.CommandHandlerNotDefined as e:
        raise command.CommandError(str(e), {"command": valid_command.command, "destination": full_destination})
    else:
      # Invalid Command
      raise command.CommandError("The received command was invalid because it specified an invalid command "+
                                 "destination.", {"command": valid_command.command, "destination": full_destination})
    
    # Verify that the command exists in the command handler
    if not hasattr(command_handler, 'command_'+valid_command.command):
      handler_string = "'"+destination+"'"
      if device_command:
        handler_string += " device"
      
      raise command.CommandError("The received command could not be located in the "+handler_string+" command handler.",
                                 {"command": valid_command.command, "destination": full_destination})
    
    if not valid_command.kernel_mode:
      # Check the user's permissions
      user_has_permission = False
      for command_permission in user_permissions['permitted_commands']:
        if (command_permission['command'] == valid_command.command and 
            command_permission['destination'] == destination):
          if 'pipelines' in command_permission:
            if pipeline is not None and pipeline in command_permission['pipelines']:
              user_has_permission = True
          else:
            user_has_permission = True
      
      if not user_has_permission:
        raise command.CommandError("You do not have permission to execute that command on that device.",
                                   {"command": valid_command.command, "destination": full_destination})

      # Check the command's session requirements
      active_user_sessions = self.session_coordinator.load_user_sessions(valid_command.user_id)
      valid_command.active_user_sessions = active_user_sessions
      if not user_permissions['ignore_session_protections']:
        # Load the command meta-data to see if it requires an active session
        try:
          command_metadata = getattr(command_handler, 'settings_'+valid_command.command)
          require_session = command_metadata()['requires_active_session']
        except AttributeError:
          # Command metadata not specified, default to True for safety
          require_session = True
        
        if require_session:
          if device_command:
            # Device command, make sure one of the user's active sessions uses the specified pipeline
            session_requirements_met = False
            for user_session in active_user_sessions:
              if user_session.active_pipeline.id == pipeline:
                session_requirements_met = True
                break
            
            if not session_requirements_met:
              raise command.CommandError("You must have a currently active session for a pipeline that contains the "+
                                         "destination device to use that command.",
                                         {"command": valid_command.command, "destination": full_destination})
          else:
            # System command, make sure the user has at least one active session
            if len(active_user_sessions) <= 0:
              raise command.CommandError("You must have an active session to use that command.",
                                         {"command": valid_command.command, "destination": full_destination})

    # Execute the command in a new thread
    command_function = getattr(command_handler, 'command_'+valid_command.command)
    command_deferred = defer.maybeDeferred(command_function, valid_command)
    command_deferred.addCallback(self._command_complete, valid_command)
    
    return command_deferred
  
  def _command_complete(self, command_results, successful_command):
    """ Builds a complete response for the successful command.
    
    This callback generates a successful command response. It is called after the command has been executed in a new
    thread. 
    
    @param command_results     A dictionary containing additional data to embed with the command response (in the
                               "result" field of the JSON response). This is returned by the individual command 
                               functions in the command handlers.
    @param successful_command  The command that just completed.
    @return Returns the constructed command response dictionary. This dictionary is fed into callbacks waiting for the
            command results.
    """
    
    command_response = successful_command.build_command_response(True, command_results)
    
    return command_response
  
  def _command_error(self, failure, failed_command):
    """ Generates an appropriate error response for the command failure.
    
    This errback generates an error response for the indicated failure, which is then loaded into a CommandFailed
    exception and re-raised. If the incoming failure is wrapping an exception of type CommandError then it may contain a 
    dictionary with additional information about the error.

    @throw Raises a CommandFailed exception which contains additional information about the failure.
    
    @param failure         The Failure object representing the error.
    @param failed_command  The Command object of the failed command.
    """
    
    # Set the error message
    error_message = {
      "error_message": str(failure.value)
    }
    
    # Check if there are any extra error parameters
    if hasattr(failure.value, 'error_parameters'):
      # Merge the parameter dictionaries
      error_results = dict(failure.value.error_parameters.items() + error_message.items())
    else:
      error_results = error_message

    # Build the response dictionary
    error_response = failed_command.build_command_response(False, error_results)

    # Log the error
    if failed_command.command:
      logging.error("A command ("+failed_command.command+") failed for the following reason: "+str(failure.value))
    else:
      logging.error("A command has failed for the following reason: "+str(failure.value))

    # Raise a CommandFailed describing the error
    raise CommandFailed(error_message['error_message'], error_response)

# High level command system exceptions
class CommandFailed(Exception):
  """ Used to wrap command execution errors.

  This exception is raised whenever a command fails to execute. It contains the error response, which specifies details
  about the error.

  @note To access the error response (what should be sent back to the user), use CommandError.response.
  """

  def __init__(self, error_message, error_response):
    """ Sets up the command error.

    @param error_message   A string describing the error. Normally, the error_response will just be used instead because 
                           it contains this string as well as additional details about the error, if there are any.
    @param error_response  A dictionary containing meta-data about the error such as the error message and any 
                           additional attributes that may have been passed with it.
    """

    self.message = error_message
    self.results = error_response

  def __str__(self):
    return self.message
