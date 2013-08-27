""" @package hwm.network.protocols.mixins
Contains mixins commonly used by the HWM network protocols.
"""

# Import required modules
from twisted.internet import reactor
from hwm.sessions import coordinator

class AuthUtilities(Object):
  """ Contains authentication related mixins used by most HWM network protocols.
  
  This class contains several authorization related methods used by the HWM network protocols. Among other things, it 
  provides methods for loading a user's certificate and locating the requested session after the TLS handshake has
  occured.
  """

  def _wait_for_session(self):
    """ Loads the requested session once the TLS handshake is complete.

    This method periodically checks if the protocol's transport has completed its TLS handshake using the 
    reactor.callLater() utility. This is required because connectionMade() method is typically called before the TLS 
    handshake has been completed. Once the handshake is complete, this method will load the requested session and set it
    as a protocol attribute.

    @note This method uses the clients's TLS certificate's common name field to determine what session it should load.
          If the requested session is not yet active, the connection will be terminated.

    @todo This method should probably wait if a user connects a few minutes before their session begins instead of 
          immediately disconnecting.
    """
    
    # Wait until the user's certificate is available
    user_cert = self.transport.getPeerCertificate()
    if user_cert is None:
      # Try again in a bit
      reactor.callLater(0.25, self._wait_for_session)
      return

    # Locate the requested session
    cert_subject = user_cert.get_subject()
    cert_reservation_id = cert_subject.commonName
    try:
      requested_session = self.session_manager.load_reservation_session(cert_reservation_id)
    except coordinator.SessionNotFound:
      # The session couldn't be found or isn't ready yet, kill the connection
      self.transport.abortConnection()
      return

    self.session = requested_session

    # Perform registrations between the session and protocol
    self._perform_registrations()
