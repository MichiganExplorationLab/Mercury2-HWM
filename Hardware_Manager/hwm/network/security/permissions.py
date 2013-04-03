""" @package hwm.network.security.permissions
This module contains a class used to manage and cache user command permissions.
"""

# Include required modules
import time, json
from jsonschema import Draft3Validator

class PermissionManager:
  """ Stores and provides access to user permission settings.
  
  This class stores user command permission settings for use by the command parser and related classes. All permission
  settings are stored with an associated timestamp. This is used to invalidate permissions after a set amount of time,
  forcing a redownload.
  """
  
  def __init__(self):
    """ Sets up the permission manager.
    """
    
    # Set up the manager attributes
    self.permissions = {}
  
  def add_user_permissions(self, user_id, permission_settings):
    """ Records permission settings for the indicated user.
    
    This method validates and saves the provided permission settings for the user.
    
    @note If the indicated user already has permission settings recorded, they will be overridden with the new settings.
    
    @throws Throws PermissionsInvalidSchema if the dictionary defined in permission_settings does not conform to the 
            permission settings schema, as checked by _validate_permissions().
    
    @param user_id              The ID of the user that the command permissions are for.
    @param permission_settings  A dictionary containing the user's command permissions and other settings.
    """
    
    # Validate the permission structure
    self._validate_permissions(permission_settings)
    
    # Permissions valid, add them for the user
    self.permissions[user_id] = permission_settings
  
  def get_user_permissions(self, user_id):
    """ Returns the permissions structure for the indicated user, if it exists.
    
    @throws Throws PermissionsUserNotFound if the specified user doesn't have any permission settings saved.
    
    @param user_id  The ID of the user to fetch permissions for.
    """
    
    # Make sure the user has some permission settings
    if user_id not in self.permissions:
      raise PermissionsUserNotFound("The indicated user does not have any permission settings saved.")
    
    # Return the permissions
    return self.permissions[user_id]
  
  def purge_user_permissions(self, age):
    """ Removes all old permission settings.
    
    This method removes all permission settings entries older than the specified value. Once the permissions have been 
    removed, calls to get_user_permissions will fail and the permissions will need to be re-downloaded.
    
    @param age  Any permission entries older than age will be purged. The age is specified in seconds.
    """
    
    # Set the current time
    current_time = int(time.time())
    
    # Loop through the permissions and purge any old entries
    for temp_user_id in self.permissions.keys():
      if (current_time - self.permissions[temp_user_id][generated_at]) >= age:
        # Delete the permission entry
        del self.permissions[temp_user_id]
  
  def _validate_permissions(self, permission_settings):
    """ Validates the provided permission settings.
    
    This method makes sure that the provided permission structure conforms to the defined JSON schema.
    
    @throws Throws PermissionsInvalidSchema if the dictionary defined in permission_settings does not conform to the 
            permission settings schema.
    
    @param permission_settings  A dictionary containing a parsed JSON permission object.
    """
    
    # Define the schema
    permission_list_schema = {
      "type": "object",
      "$schema": "http://json-schema.org/draft-03/schema",
      "required": True,
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
              "device_id": {
                "type": "string",
                "id": "device_id",
                "required": False
              }
            }
          }
        }
      }
    }
  
    # Validate the JSON schema
    schema_validator = Draft3Validator(permission_list_schema)
    try:
      schema_validator.validate(permission_settings)
    except:
      # Invalid permission list JSON
      raise PermissionsInvalidSchema("The provided permission list did not conform to the defined schema.")

class PermissionsInvalidSchema(Exception):
  pass
class PermissionsUserNotFound(Exception):
  pass
