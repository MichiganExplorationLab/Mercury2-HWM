""" @package hwm.network.security.permissions
This module contains a class used to manage and cache user command permissions.
"""

# Include required modules
import time, json, jsonschema, urllib2, urllib
from twisted.internet import threads, defer
from hwm.core import configuration

class PermissionManager:
  """ Stores and provides access to user permission settings.
  
  This class stores user command permission settings for use by the command parser and related classes. All permission
  settings are stored with an associated timestamp. This is used to invalidate permissions after a set amount of time,
  forcing a redownload.
  """
  
  def __init__(self, permissions_endpoint, update_frequency):
    """ Sets up the permission manager.
    
    @param permissions_endpoint  The location that can be queried to find user command permissions. This can either be
                                 the mercury2 user interface API or a file. If this points to the mercury2 API, it must 
                                 start with http or https.
    @param update_frequency      How often the user's permissions should be updated (i.e. if a user's permissions are 
                                 requested and they are older than this value, update them). Specified in seconds.
    """
    
    # Set up the manager attributes
    self.permissions = {}
    self.use_remote_permissions = permissions_endpoint.startswith('http')
    self.permissions_location = permissions_endpoint
    self.config = configuration.Configuration
    self.update_frequency = update_frequency
  
  def get_user_permissions(self, user_id):
    """ Returns the permissions structure for the indicated user.
    
    If the user does not have any permissions loaded, they will be downloaded/loaded in a thread and returned via a 
    deferred. If the user does have permissions in the system, they will be fired immediately into the returned 
    deferred (and get updated in the background if they are too old).
    
    @note The permissions returned from this function are a copy. That is, they don't reference the permission manager's
          main permission dictionary.
    
    @throws Throws PermissionsUserNotFound if the specified user doesn't have any permission settings saved.
    
    @param user_id  The ID of the user to fetch permissions for. This refers to the UUID that was generated for the 
                    user, not their username.
    @return Returns a deferred that will be fired with the user's permissions (or an error, if one occurs). 
    """
    
    # Local variables
    current_time = int(time.time())
    permissions_deferred = None
    
    # Check if the user has cached permissions
    if user_id not in self.permissions:
      # Update the user's permissions and return the results in a deferred
      permissions_deferred = self._update_user_permissions(user_id)
    else:
      # Update the permissions in the background, if needed
      if (current_time - self.permissions[user_id]['loaded_at']) >= self.update_frequency:
        background_deferred = self._update_user_permissions(user_id)
        background_deferred.addErrback(self._background_update_error)
      
      # Create a deferred and fire the user's cached permissions into it
      permissions_deferred = defer.succeed(self.permissions[user_id].copy())
    
    # Return the user's permissions via a deferred
    return permissions_deferred
  
  def purge_user_permissions(self, age):
    """ Removes all old permission settings.
    
    This method removes all permission settings entries older than the specified value. Once the permissions have been 
    removed, calls to get_user_permissions will fail and the permissions will need to be re-downloaded.
    
    @note The preferred way to update user permissions is to simply let get_user_permissions do it automatically. It 
          will return the old cached user permissions while they're being updated. If purge_user_permissions is used 
          instead, the deferred returned from get_user_permissions will take longer more often as the permissions are
          being updated.
    
    @param age  Any permission entries older than age will be purged. The age is specified in seconds.
    """
    
    # Set the current time
    current_time = int(time.time())
    
    # Loop through the permissions and purge any old entries
    for temp_user_id in self.permissions.keys():
      if (current_time - self.permissions[temp_user_id]['loaded_at']) >= age:
        # Delete the permission entry
        del self.permissions[temp_user_id]
  
  def _update_user_permissions(self, user_id):
    """ Updates the permissions for the indicated user.
    
    This method downloads (or loads), validates, and saves the specified user's permission settings.
    
    @note If a non-remote permissions endpoint is specified, the permissions will be loaded from the offline local file.
    @note If the indicated user already has permission settings recorded, they will be overridden with the new settings.
    
    @throws Throws PermissionsInvalidSchema if the dictionary defined in permission_settings does not conform to the 
            permission settings schema, as checked by _validate_permissions().
    @throws PermissionsUserNotFound if the indicated user couldn't be located in the loaded permissions resource.
    
    @param user_id  The ID of the user that the command permissions are for.
    @return Returns a deferred that will be fired with the results of the permission settings load/download. That is,
            an error or the permissions object for the indicated user.
    """
    
    # Attempt to load the user's permissions
    if self.use_remote_permissions:
      defer_download = threads.deferToThread(self._download_remote_permissions, user_id)
    else:
      defer_download = threads.deferToThread(self._load_local_permissions, user_id)
    
    # Validate & save
    defer_download.addCallback(self._validate_permissions, user_id)
    defer_download.addCallback(self._save_permissions, user_id)
    
    return defer_download
  
  def _download_remote_permissions(self, user_id):
    """ Loads the user's permissions from a remote location.
    
    This method loads the specified user's command execution permissions from a remote location (e.g. the mercury2 
    user interface) and returns them.
    
    @throws PermissionsError if an error occurs while downloading or parsing the schedule.
    @throws May throw PermissionsInvalidSchema if the permission settings do not conform to the defined schema.
    
    @note This method is intended to be called with threads.deferToThread. The returned permissions will be passed to 
          the resulting deferred's callback chain.
    
    @param user_id  The ID of the user we want to download permissions for.
    @return Returns an array of JSON objects representing the permissions for each queried user. Note that in this case
            the array will only have a single element.
    """
    
    # Setup local variables
    permissions_file = None
    
    # Attempt to download the JSON resource
    try:
      # Encode the request parameters
      encoded_params = urllib.urlencode({'user_id': user_id})
      
      permissions_request = urllib2.Request(self.permissions_location+'?'+encoded_params)
      permissions_opener = urllib2.build_opener()
      permissions_file = permissions_opener.open(permissions_request, None, self.config.get('permissions-update-timeout'))
    except:
      # Error downloading the file
      raise PermissionsError('There was an error downloading the permissions for user: '+user_id)
    
    return permissions_file
  
  def _load_local_permissions(self, user_id):
    """ Load the user's permissions from a local file.
    
    This method loads the specified user's command execution permissions from a local master permissions file (generated
    by the mercury2 user interface). 
    
    @throws PermissionsError if the file can't be loaded for some reason.
    @throws May throw PermissionsInvalidSchema if the permission settings file does not conform to the defined schema.
    
    @note This method is intended to be called with threads.deferToThread. The returned permissions will be passed to the 
          resulting deferred's callback chain.
    
    @param user_id  The ID of the user to load permissions for.
    @return Returns an array of JSON objects representing the permissions for each queried user. Note that in this case
            the array will only have a single element.
    """
    
    # Setup local variables
    permissions_file = None
    
    # Attempt to open the permissions file
    try:
      permissions_file = open(self.permissions_location, 'r')
    except IOError:
      # Error loading the file
      raise PermissionsError('There was an error loading the user permissions file.')
    
    return permissions_file
  
  def _background_update_error(self, update_error):
    """ This callback responds to errors when updating the permissions in the background.
    
    @param update_error  A Failure object containing the error.
    @return Simply returns True to keep the error from getting collected. 
    """
    
    return True
  
  def _save_permissions(self, permission_settings, user_id):
    """ Saves the user command execution permission settings in the PermissionManager.
    
    This callback saves the permissions for every user with permissions defined in permission settings.
    
    @note Depending on how the permissions are loaded (i.e. either from a remote API location or a local offline file),
          permission_settings can contain the permissions for multiple users. Regardless of how many users are
          represented in permission_settings, the permissions will be saved for all of them. This prevents frequent file
          loads when operating in offline mode.
    @note If a user already has non-expired permissions in the manager, they will be overwritten by the new values.
    
    @throws PermissionsUserNotFound if the user originally indicated couldn't be located in the loaded permissions
            resource.
    
    @param permission_settings  An array containing the JSON permission objects for users it includes.
    @param user_id              The ID of the user that was initially queried for.
    @return Returns the permission settings for the user that was originally queried for.
    """
    
    target_user_permissions = None
    current_time = int(time.time())
    
    # Loop through and save every permission object
    for user_permissions in permission_settings:
      self.permissions[user_permissions['user_id']] = user_permissions
      
      # Set the load time
      self.permissions[user_permissions['user_id']]['loaded_at'] = current_time
      
      if user_permissions['user_id'] == user_id:
        target_user_permissions = user_permissions
    
    # Make sure the original user's permissions were downloaded
    if target_user_permissions is None:
      raise PermissionsUserNotFound("The permissions for user '"+user_id+"' could not be found upon loading the latest "
                                    "version of the permissions resource.")
    
    # Return a copy of the user's permission
    return target_user_permissions.copy()
  
  def _validate_permissions(self, raw_permissions, user_id):
    """ Validates the provided permission settings.
    
    This method makes sure that the provided permission structure conforms to the defined JSON schema.
    
    @throws Throws PermissionsInvalidSchema if the dictionary defined in permission_settings does not conform to the 
            permission settings schema.
    @throws Throws PermissionsError if the raw permissions resource can't be parsed.
    
    @param raw_permissions  A raw, unparsed, permissions resource file (either from net or local machine).
    @param user_id          The ID of the user who's permissions are being queried for.
    @return Returns a dictionary containing the parsed permissions.
    """
    
    # Parse the schedule JSON
    try:
      permission_settings = json.load(raw_permissions)
    except ValueError:
      # Error parsing the permissions JSON
      raise PermissionsError('The permissions resource for user \''+user_id+'\' did not contain a parsable JSON object.')
    
    # Define the schema
    permission_list_schema = {
      "type": "array",
      "$schema": "http://json-schema.org/draft-03/schema",
      "required": True,
      "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
          "generated_at": {
            "type": "number",
            "id": "generated_at",
            "required": True
          },
          "user_id": {
            "type": "string",
            "id": "user_id",
            "required": True
          },
          "username": {
            "type": "string",
            "id": "username",
            "required": True
          },
          "ignore_session_protections": {
            "type": "boolean",
            "id": "ignore_session_protections",
            "required": False
          },
          "permitted_commands": {
            "type": "array",
            "id": "permitted_commands",
            "required": True,
            "items": {
              "type": "object",
              "additionalProperties": True,
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
                }
              }
            }
          }
        }
      }
    }
  
    # Validate the JSON schema
    schema_validator = jsonschema.Draft3Validator(permission_list_schema)
    try:
      schema_validator.validate(permission_settings)
    except jsonschema.ValidationError:
      # Invalid permission list JSON
      raise PermissionsInvalidSchema("The provided permission list did not conform to the defined schema.")
    
    return permission_settings

# Define permission related exceptions
class PermissionsInvalidSchema(Exception):
  pass
class PermissionsUserNotFound(Exception):
  pass
class PermissionsError(Exception):
  pass

