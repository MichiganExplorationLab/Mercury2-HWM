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
