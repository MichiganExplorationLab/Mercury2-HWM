""" @package hwm.command.parser
Parses system and hardware commands and passes them to the appropriate command handler.

This module contains a class that validates, parses, and delegates ground station commands to the appropriate handler 
as they're received. Once a command has been executed, it returns the results of the command.
"""

# Import required modules
import time, logging
from twisted.internet import defer, threads
from hwm.command import command

class CommandParser:
  """ Processes all commands received by the hardware manager.
  
  This class parses and performs validations on received commands, delegating them to the appropriate handler when
  appropriate.
  """
  
  def __init__(self, system_command_handlers, permission_manager):
    """ Sets up the command parser instance.
    
    @param system_command_handlers  A dictionary containing references to all of the system command handlers. If a
                                    command's destination field references an element in this dictionary, that command
                                    handler will be used. Otherwise, it will be delegated to a device command handler.
    @param permission_manager       A reference to the user permission manager.
    """
    
    # Set the class attributes
    self.system_command_handlers = system_command_handlers
    self.permission_manager = permission_manager

  def parse_command(self, raw_command, user_id):
    """ Processes all commands received by the ground station.
    
    When a raw command is passed to this function, it performs the following operations via a series of callbacks:
    * Constructs a new Command and validates it against that command's schema
    * Verifies that the indicated command exists
    * Checks that the user can execute the command
    * Executes the command in a new thread
    * Returns a deferred that will be fired with the results of the command
    
    @note In the event of an error with the command (e.g. invalid json or permission error), the error will be logged
          and an error response will be returned ready for transmission.
    @note Even if the command generates an error response, the returned deferred's callback chain will be called with
          the contents of the error (instead of the errback chain). 
    @note The callback chain from the deferred returned from this function will return a dictionary representing the 
          results of the command. The 'response' key will contain a string with the results of the command (in JSON).
    @note The actual command execution occurs in a new thread. Make sure that command code is thread safe!
    
    @param raw_command  A raw command string containing metadata about the command in an arbitrary format.
    @param user_id      The user's ID for the purpose of loading command execution settings. This probably came from 
                        the user's SSL certificate.
    @return Returns the results of the command (in JSON) using a deferred. May be the output of the command or an error 
            message.
    """
    
    # Local variables
    time_command_received = time.time()
    new_command = None
    
    # Create the new command
    new_command = command.Command(time_command_received, raw_command, user_id)
    
    # Asynchronously validate the command (format and schema)
    validation_deferred = new_command.validate_command()
    
    # Add callbacks to handle validation results (_command_error added second so it can handle errors from _run_command)
    validation_deferred.addCallback(self._run_command, new_command)
    validation_deferred.addErrback(self._command_error, new_command)
    
    return validation_deferred
  
  def _run_command(self, validation_results, valid_command):
    """ Continues executing a command after it has been validated.
    
    This callback continues to validate and execute a command after it has passed preliminary format and schema 
    validations. 
    
    @note This callback returns a deferred which means that the parent deferred's callback chain will pause until the 
          returned deferred has been fired. The returned deferred's callbacks will then execute before the remaining 
          callbacks on the parent deferred.
    
    @throw This callback may throw several exceptions indicating errors about the command. These exceptions will 
           automatically be picked up by the errback chain on the parent deferred.
    
    @param validation_results  The validation results. Always true (because this is a callback and not an errback).
    @param valid_command       The Command object being executed.
    @return Returns a deferred that will eventually be fired with the user's command execution permissions.
    """
    
    # Fetch the user's permissions
    permission_load_deferred = self.permission_manager.get_user_permissions(valid_command.user_id)
    permission_load_deferred.addCallback(self._run_command_continue, valid_command)
    
    return permission_load_deferred
  
  def _run_command_continue(self, user_permissions, valid_command):
    """ Continues command execution after the user's permissions have been retrieved.
    
    @param user_permissions  A dictionary containing the user's permissions.
    @param valid_command     The Command object for the currently executing command.
    @return Returns a deferred that will eventually be fired with the results of the command execution.
    """
    
    # Determine where to send the command
    device_command = False
    command_handler = None
    if valid_command.destination in self.system_command_handlers:
      command_handler = self.system_command_handlers[valid_command.destination]
    else:
      device_command = True
      print 'LOAD DEVICE COMMAND HANDLER'
    
    # Verify that the command exists
    if not hasattr(command_handler, 'command_'+valid_command.command):
      handler_string = "'"+valid_command.destination+"'"
      if device_command:
        handler_string += " device"
      
      raise command.CommandError("The received command could not be located in the "+handler_string+" command handler.",
                                 {"invalid_command": valid_command.command})
    
    # Check the user command execution permissions
    user_has_permission = False
    for command_permission in user_permissions['permitted_commands']:
      if (command_permission['command'] == valid_command.command and 
          command_permission['destination'] == valid_command.destination):
        user_has_permission = True
    
    if not user_has_permission:
      raise command.CommandError("You do not have permission to execute that command.",
                                 {"restricted_command": valid_command.command})
    
    # Check the command's session requirements
    # TODO
    
    # Execute the command in a new thread
    command_deferred = threads.deferToThread(getattr(command_handler, 'command_'+valid_command.command), valid_command)
    command_deferred.addCallback(self._command_complete, valid_command)
    command_deferred.addErrback(self._command_error, valid_command) # Is this necessary or will it get picked up by parent?
    
    return command_deferred
  
  def _command_complete(self, command_results, successful_command):
    """ Builds a complete response for the successful command.
    
    This callback generates a successful command response. It is called after the command has been executed in a new
    thread. 
    
    @param command_results    A dictionary containing additional data to embed with the command response (in the
                              "result" field of the JSON response). This is returned by the individual command functions
                              in the command handlers.
    @param successful_command  The command that just completed.
    @return Returns the constructed command response dictionary. This dictionary is fed into following callbacks.
    """
    
    command_response = successful_command.build_command_response(True, command_results)
    
    return command_response
  
  def _command_error(self, failure, failed_command):
    """ Generates an appropriate error response for the failure.
    
    This errback generates an error response for the indicated failure, which it then returns (thus passing the error
    response to the callback chain of the deferred returned from parse_command). If the failure is wrapping an exception
    of type CommandError then it may contain a dictionary with additional information about the error.
    
    @param failure         The Failure object representing the error.
    @param failed_command  The Command object of the failed command.
    @return Returns a dictionary containing information about the request.
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
    
    # Build the response
    error_response = failed_command.build_command_response(False, error_results)
    
    # Log the error
    if failed_command.command:
      logging.error("A command ("+failed_command.command+") failed for the following reason: "+str(failure.value))
    else:
      logging.error("A command has failed for the following reason: "+str(failure.value))
    
    # Return the error response dictionary back into the callback chain
    return error_response
