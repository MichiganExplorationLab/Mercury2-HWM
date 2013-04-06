# Import required modules
import logging, time, json
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from twisted.test import proto_helpers
from hwm.core.configuration import *
from hwm.network.security import permissions

class TestPermissionManager(unittest.TestCase):
  """ This test suite tests the permission manager class, which is used to manage and cache downloaded user command
  execution permissions.
  """
  
  def setUp(self):
    # Set a local reference to Configuration (how other modules should typically access Config)
    self.config = Configuration
    self.config.verbose_startup = False
    
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self.config.options = {}
    self.config.user_options = {}
    
    # Reset the object references
    self.config = None
  
  def test_local_file_load_missing(self):
    """ Verifies that the correct error is generated when the offline permissions file can't be found.
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_doesnt_exist.json')
    
    # Force a file load
    update_deferred = permission_manager.add_user_permissions('test_user')
    
    return self.assertFailure(update_deferred, permissions.PermissionsError)
  
  def test_local_file_load_invalid(self):
    """ Checks that the permissions manager correctly rejects a schedule containing invalid JSON (doesn't conform to the
    schema).
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_invalid.json')
    
    # Force a file load
    update_deferred = permission_manager.add_user_permissions('test_admin')
    
    return self.assertFailure(update_deferred, permissions.PermissionsInvalidSchema)
  
  def test_add_valid_user(self):
    """ Tests that a valid user can be added from a local permissions file successfully.
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json')
    
    def user_permissions_callback(permission_settings):
      # Check both valid users can be accessed
      test_admin = permission_manager.get_user_permissions('test_admin')
      
      # Verify that the permissions were loaded
      self.assertEqual(test_admin['user_id'], 'test_admin')
      self.assertEqual(len(test_admin['permitted_commands']), 2) 
    
    # Force a file load
    update_deferred = permission_manager.add_user_permissions('test_admin')
    update_deferred.addCallback(user_permissions_callback)
    
    return update_deferred
  
  def test_add_invalid_user(self):
    """ Attempt to add an invalid user from a valid permissions file (i.e. a user not defined in the file).
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json')
    
    # Force a file load
    update_deferred = permission_manager.add_user_permissions('test_doesnt_exist')
    
    return self.assertFailure(update_deferred, permissions.PermissionsUserNotFound)
  
  def test_get_invalid_user(self):
    """ Makes sure that the correct error is returned when an invalid user is requested.
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json')
    
    def user_permissions_callback(permission_settings):
      # Try to access an invalid user
      self.assertRaises(permissions.PermissionsUserNotFound, permission_manager.get_user_permissions, 'test_doesnt_exist')
    
    # Force a file load
    update_deferred = permission_manager.add_user_permissions('test_admin')
    update_deferred.addCallback(user_permissions_callback)
    
    return update_deferred
  
  def test_old_permissions_purge(self):
    """ Verifies that the purge method correctly removes old permission entries (which would force a reload).
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json')
    
    def user_permissions_callback(permission_settings):
      # Verify we can access the expired permissions before the purge
      test_user = permission_manager.get_user_permissions('test_user')
      
      # Purge the old permissions (older than 1 hour)
      permission_manager.purge_user_permissions(3600)
      
      # Make sure the permissions were purged
      self.assertRaises(permissions.PermissionsUserNotFound, permission_manager.get_user_permissions, 'test_user')
    
    # Force a file load
    update_deferred = permission_manager.add_user_permissions('test_user')
    update_deferred.addCallback(user_permissions_callback)
    
    return update_deferred
    
    
