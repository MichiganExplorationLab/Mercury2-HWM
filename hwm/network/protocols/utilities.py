""" @package hwm.network.protocols.utilities
Contains methods commonly used by the HWM network protocols.
"""

# Import required modules
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from hwm.sessions import coordinator

def load_session_after_tls_handshake(protocol):
  """ Loads the requested session once the provided Protocol's TLS handshake is complete.

  This function periodically checks if the specified protocol's transport has completed its TLS handshake using the 
  reactor.callLater() utility. This is required because connectionMade() method is typically called before the TLS 
  handshake has been completed. Once the handshake is complete, this function will load the requested session and return
  it via a deferred.

  @note This function uses the clients's TLS certificate's common name field to determine what session it should load.
        If the requested session is not yet active, the connection will be terminated.

  @todo This method should probably wait if a user connects a few minutes before their session begins instead of 
        immediately disconnecting.

  @param protocol  The Protocol that wants to wait for its TLS handshake to complete.
  @return This function returns a deferred that will eventually be fired with the loaded session. If the session can't 
          be located, the deferred will errback.
  """
  
  # Try to load the client's TLS certificate
  user_cert = protocol.transport.getPeerCertificate()
  if user_cert is None:
    # Create a deferred and schedule it to fire in a bit so we can check for the certificate again
    recheck_deferred = Deferred()
    recheck_deferred.addCallback(load_session_after_tls_handshake)
    reactor.callLater(0.25, recheck_deferred.callback, protocol)
    return recheck_deferred

  # Locate the requested session
  cert_subject = user_cert.get_subject()
  cert_reservation_id = cert_subject.commonName
  try:
    requested_session = protocol.session_coordinator.load_reservation_session(cert_reservation_id)
  except coordinator.SessionNotFound as lookup_error:
    # The session couldn't be found or isn't ready yet, return a failed deferred
    failed_deferred = Deferred()
    failed_deferred.errback(lookup_error)
    return failed_deferred

  # Return a deferred fired with the loaded session
  session_deferred = Deferred()
  session_deferred.callback(requested_session)
  return session_deferred
