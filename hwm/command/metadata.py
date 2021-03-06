""" @package hwm.command.metadata
This module contains functions used to build a command's meta-data dictionary. This dictionary defines how to reach a 
specific command, what parameters it accepts, and whether or not it requires an active session to run.

Periodically, a command's meta-data dictionary is loaded by the system state packager which then serializes it and sends
it to the user interface. The user interface will use the metadata to build an appropriate form to allow the user to 
easily execute the command.
"""

def build_metadata_dict(command_parameters, command_id, command_handler_name, requires_active_session = True,
                        dangerous = True, schedulable = False, use_as_initial_value = False):
  """ Builds the command meta-data structure for a specific command.
  
  Command handlers use this function to build the command meta-data structures for the commands they service. For the 
  most part, all command meta-data structures must be built using this command. If a command meta-data structure does
  not conform to this format, an error will be generated by the status packager or the user interface won't be able to 
  construct a form for it.
  
  @throws May throw InvalidCommandParameters in the event that the supplied parameter dictionary isn't valid.
  @throws May throw InvalidCommandAddress if neither command_handler_name or device_id are set.
  
  @param command_parameters       An array of dictionaries containing the parameters that the command accepts along with
                                  any basic restrictions on the parameter value. Currently, the following types and 
                                  restrictions are supported:
                                  
                                  - type: string
                                      + minlength    - The min length of the string (integer)
                                      + maxlength    - The max length of the string (integer)
                                  - type: number
                                      + minvalue     - The minimum value of the number (inclusive, integer)
                                      + maxvalue     - The maximum value of the number (inclusive, integer)
                                      + integer      - Whether or not the number must be an integer (boolean)
                                  - type: boolean
                                  - type: select
                                      + multiselect  - Whether or not multiple options can be selected (boolean)
                                      + options      - An array containing valid [title, value] pairs for the argument 
                                                       (required for select, array)
                                  - Any Type
                                      + required     - Whether or not the argument is required to submit the command 
                                                       (boolean)
                                      + description  - A description of the argument (string)
                                      + title        - A short title for the argument (required, string)
                                  
                                  If a restriction is left blank, the user interface will use a default value. 
                                  Unrecognized/unsupported attributes will be ignored (but allowed).
  @param command_id               The ID of the command. This must be unique per command handler.
  @param command_handler_name     The name of the system command handler that the command is located in. This is used by
                                  user interface to address user commands to the appropriate handler. If the command is
                                  a device command, then this will be the device ID.
  @param requires_active_session  Whether or not the command requires an active session to be executed. If the command 
                                  is a system command, then the command handler must perform its own validations on the 
                                  session. If the command is a device command, the command parser will make sure that
                                  the user has an active session with a pipeline that uses the hardware device before
                                  executing the command (and the command handler may perform any additional validations 
                                  on its own if needed).
  @param dangerous                If the command is dangerous, it could possibly dangerously modify the ground station 
                                  state (e.g. turn of devices, delete sessions, etc.). This flag will cause the user
                                  interface to restrict access to the command by default (which can be overridden if
                                  desired).
  @param schedulable              Indicates that the command can be scheduled using the reservation scheduling service 
                                  (if the active pipeline supports it). If it can, the user interface will use this to 
                                  build a form to schedule this command during the reservation process.
  @param use_as_initial_value     If set, the user interface will use this command when building the device or system's
                                  initial state configuration forms during the reservation process. This can be used, 
                                  for example, to set the initial frequency that a radio should be tunned to.
  @return Returns a dictionary containing the command meta-data.
  """
  
  metadata = {}
  
  # Verify that an address has been set
  if command_handler_name is None:
    raise InvalidCommandAddress("The command's handler was not specified.")
  
  # Validate the parameter metadata
  if not command_id:
    raise InvalidCommandMetadata("A valid command ID was not specified.")
  for parameter in command_parameters:
    if 'type' not in parameter or 'title' not in parameter:
      raise InvalidCommandMetadata("A parameter did not specify a type or title.")
    if parameter['type'] not in ['string', 'number', 'boolean', 'select']:
      raise InvalidCommandMetadata("Invalid command parameter type specified: "+parameter['type'])
    
    # If the parameter is a select, make sure it provides at least one option and that all provided options are valid
    if parameter['type'] == 'select':
      if 'options' not in parameter or len(parameter['options']) <= 0:
        raise InvalidCommandMetadata("No options specified for 'select' command parameter.")
      
      for option in parameter['options']:
        if not isinstance(option, list) or len(option) != 2:
          raise InvalidCommandMetadata("One of the options specified for a 'select' parameter was malformed. Options need to be a 2 element list containing the option title and value.")
  
  # Store the meta-data values
  metadata['command_id'] = command_id
  metadata['destination'] = command_handler_name
  metadata['parameters'] = command_parameters
  metadata['requires_active_session'] = True if requires_active_session else False
  metadata['dangerous'] = True if dangerous else False
  metadata['schedulable'] = True if schedulable else False
  metadata['use_as_initial_value'] = True if use_as_initial_value else False
  
  return metadata;

class InvalidCommandMetadata(Exception):
  pass
class InvalidCommandAddress(Exception):
  pass
