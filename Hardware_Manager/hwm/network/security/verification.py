""" @package hwm.network.security.verification
Contains functions for verifying user authorization credentials.

This module functions for authenticating users based on their provided SSL certificate.
"""

# Import required modules
import logging
from hwm.core.configuration import Configuration
from OpenSSL import SSL
from twisted.internet import ssl

def authentication_callback(connection, x509, errnum, errdepth, ok):
  """ Called when a user SSL certificate can't be authenticated.
  
  @param connection  Relevant connection object.
  @param x509        SSL certificate information.
  @param errnum      Number of errors encountered.
  @param errdepth    How deep the errors go?
  @param ok          Whether or not the authentication was successful or not.
  """
  
  # Simply verify that the SSL validation worked
  if not ok:
    logging.error("Authentication Error - A user's SSL certificates could not be authenticated: "+x509.get_subject().commonName.decode())
    return False
  
  return True

def create_ssl_context_factory():
  """ Creates and returns a new ssl.DefaultOpenSSLContextFactory for securing various station connections.
  
  @return Returns an SSL context factory for use by SSL listeners.
  """
  
  # Create the SSL context
  server_context_factory = ssl.DefaultOpenSSLContextFactory(Configuration.get('ssl-private-key-location'), Configuration.get('ssl-public-cert-location'))
  server_context = server_context_factory.getContext()
  server_context.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT, authentication_callback)
  
  return server_context_factory
