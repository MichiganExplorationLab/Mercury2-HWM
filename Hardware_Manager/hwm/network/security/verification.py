""" @package hwm.network.security.verification
Contains functions for verifying user authorization credentials.

This module functions for authenticating users based on their provided SSL certificate.
"""

def authentication_callback(connection, x509, errnum, errdepth, ok):
  """ Called when a user SSL certificate can't be authenticated.
  
  @param connection  Relevant connection object.
  @param x509        SSL certificate information.
  @param errnum      Number of errors encountered.
  @param errdepth    How deep the errors go?
  @param ok          Whether or not the authentication was successful or not.
  """
  
  print "SSL Certificate Authenticated"

def validate_permission_list(self, permission_load_result):
  """ Validates a user command permission list downloaded from the user interface. 
  
  This callback validates the format of the downloaded permission list against the defined schema.
  
  @throw Throws InvalidSchema if the permission list stored in permission_load_result doesn't conform to the schema.
  
  @param permission_load_result  The raw permission list object.
  @retun Returns a python object representing the permission list.
  """
  
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
    schema_validator.validate(permission_load_result)
  except:
    # Invalid permission list JSON
    logging.error("The downloaded command permission list did not conform to the JSON schema.")
    raise InvalidSchema("The downloaded command permission list did not conform to the JSON schema.")
  
  return permission_load_result

class InvalidSchema(Exception):
  pass
