""" @package hwm.network.security.verification
Contains functions for verifying user authorization credentials.

This module functions for authenticating users based on their provided SSL certificate.
"""

# Import required modules
import logging
from hwm.core.configuration import Configuration
from OpenSSL import SSL
from twisted.internet import ssl

def create_tls_context_factory():
  """ Creates and returns a new ssl.ContextFactory used to create TLS contexts for various ground station connections.
  
  This method initializes a TLS context factory that uses the HWM instance's private key and public certificate 
  (specified by 'tls-private-key-location' and 'tls-public-cert-location', respectively). These files uniquely identify 
  the HWM instance and are typically generated and signed by the user interface. In addition, it also initializes the 
  TLS context factory with the ground station's public CA certificate which is used to verify the integrity of user 
  certificates. 

  @return Returns an ssl.ContextFactory for use by SSL listeners.
  """

  # Load the server's private key, public X509 certificate, and the certificate authority's X509 certificate
  with open(Configuration.get('tls-ca-cert-location')) as ca_certificate_file:
    ca_certificate = ssl.Certificate.loadPEM(ca_certificate_file.read())
  with (open(Configuration.get('tls-private-key-location')) as private_key_file, 
        open(Configuration.get('tls-public-cert-location')) as public_certificate_file):
    server_certificate = ssl.PrivateCertificate.loadPEM(private_key_file.read() + public_certificate_file.read())

  server_context_factory = server_certificate.options(ca_certificate)

  return server_context_factory
