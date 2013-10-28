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
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_doesnt_exist.json', 3600)
    
    # Force a file load
    update_deferred = permission_manager.get_user_permissions('2')
    
    return self.assertFailure(update_deferred, permissions.PermissionsError)
  
  def test_local_file_load_invalid(self):
    """ Checks that the permissions manager correctly rejects a schedule containing invalid JSON (doesn't conform to the
    schema).
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_invalid.json', 3600)
    
    # Force a file load
    update_deferred = permission_manager.get_user_permissions('1')
    
    return self.assertFailure(update_deferred, permissions.PermissionsInvalidSchema)
  
  def test_get_valid_new_user(self):
    """ Tests that a valid non-resident (i.e. not cached) user can be loaded and returned from a local permissions file 
    successfully.
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json', 3600)
    
    def user_permissions_callback(permission_settings):
      # Verify that the returned permissions are correct
      self.assertEqual(permission_settings['user_id'], '1')
      self.assertEqual(len(permission_settings['permitted_commands']), 3) 
      
      # Manually make sure the permissions were saved
      self.assertEqual(permission_manager.permissions['1']['username'], 'test_admin')
      self.assertEqual(len(permission_manager.permissions['1']['permitted_commands']), 3) 
    
    # Force a file load
    update_deferred = permission_manager.get_user_permissions('1')
    update_deferred.addCallback(user_permissions_callback)
    
    return update_deferred
  
  def test_get_valid_old_user(self):
    """ Verifies that the permissions manager correctly returns the cached permissions in the event that they need to be
    updated (instead of waiting for the new ones).
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json', 3600)
    
    def check_permission_update(permission_settings):
      # Check that the old version of the user's permissions were returned while they're being updated
      self.assertTrue(permission_manager.permissions['2']['loaded_at'] == 42, "A user's cached permissions weren't returned as expected.")
    
    def user_permissions_callback(permission_settings):
      # Reset the loaded_at time for the user to be older than the update interval for the permission manager
      permission_manager.permissions['2']['loaded_at'] = 42
      
      # Get the user's permissions
      reload_deferred = permission_manager.get_user_permissions('2')
      reload_deferred.addCallback(check_permission_update)
    
    # Force a file load
    update_deferred = permission_manager.get_user_permissions('1')
    update_deferred.addCallback(user_permissions_callback)
    
    return update_deferred
  
  def test_background_update_error_handling(self):
    """ Tests that errors are correctly handled when a background update thread fails.
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json', 3600)
    
    def check_permission_update(permission_settings):
      # Check that the old version of the user's permissions was returned because the update should have failed
      self.assertTrue(permission_manager.permissions['2']['loaded_at'] == 42, "A user's cached permissions weren't returned as expected.")
    
    def user_permissions_callback(permission_settings):
      # Reset the loaded_at time for the user to be older than the update interval for the permission manager
      permission_manager.permissions['2']['loaded_at'] = 42
      
      # Update the endpoint to be invalid (trial will fail if the update deferred doesn't get cleaned up)
      permission_manager.permissions_location = self.source_data_directory+'/network/security/tests/data/test_permissions_doesnt_exist.json'
      
      # Get the user's permissions
      reload_deferred = permission_manager.get_user_permissions('2')
      reload_deferred.addCallback(check_permission_update)
      
    # Force a file load
    update_deferred = permission_manager.get_user_permissions('1')
    update_deferred.addCallback(user_permissions_callback)
    
    return update_deferred
  
  def test_get_invalid_user(self):
    """ Attempt to get an invalid user from a valid permissions file (i.e. a user not defined in the file).
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json', 3600)
    
    # Force a file load
    update_deferred = permission_manager.get_user_permissions('99')
    
    return self.assertFailure(update_deferred, permissions.PermissionsUserNotFound)
  
  def test_old_permissions_purge(self):
    """ Verifies that the purge method correctly removes old permission entries.
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json', 3600)
    
    def user_permissions_callback(permission_settings):
      # Verify that the permissions are in the dictionary before the purge
      self.assertTrue('2' in permission_manager.permissions, "The user's permissions weren't correctly saved after a load.")
      
      # Modify the loaded_at age for the purge to work
      permission_manager.permissions['2']['loaded_at'] = int(time.time())-5000
      
      # Purge the old permissions (older than 1 hour)
      permission_manager.purge_user_permissions(3600)
      
      # Make sure the permissions were purged
      self.assertTrue('2' not in permission_manager.permissions, "A user's permissions weren't correctly purged.")
    
    # Force a file load
    update_deferred = permission_manager.get_user_permissions('2')
    update_deferred.addCallback(user_permissions_callback)
    
    return update_deferred
    
    
