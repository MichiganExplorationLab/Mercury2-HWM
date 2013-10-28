# Import required modules
import logging
from mock import MagicMock
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from hwm.network.protocols import utilities
from hwm.sessions import session, coordinator

class TestProtocolUtilities(unittest.TestCase):
  """ This test suite tests the various utility and functions used by the hardware manager protocols. 
  """
  
  def setUp(self):
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")

    # Disable logging for most events
    logging.disable(logging.CRITICAL)

  def test_load_session_after_tls_handshake_success(self):
    """ This test verifies that the utilities.load_session_after_tls_handshake() function can correctly wait for the TLS
    handshake to complete, load the requested session, and return it via a deferred.
    """

    # Create a mock protocol and session to test with
    test_res_id = "res_id"
    test_protocol = MagicMock()
    test_session = MagicMock()
    test_protocol.transport.getPeerCertificate = lambda : None
    test_protocol.session_coordinator.load_reservation_session = lambda res_id: test_session

    def validate_session(loaded_session):
      """ A callback that will receive the session once the simulated TLS handshake finishes.
      """

      self.assertEqual(loaded_session, test_session)

    # Try to load the session (should trigger a reactor.callLater call because no certificate was returned)
    session_deferred = utilities.load_session_after_tls_handshake(test_protocol)
    session_deferred.addCallback(validate_session)

    # Update the getPeerCertificate method to return a mock certificate before the reactor.callLater call goes out
    test_cert = MagicMock()
    test_subject = MagicMock()
    test_subject.commonName = test_res_id
    test_cert.get_subject = lambda : test_subject
    test_protocol.transport.getPeerCertificate = lambda : test_cert

    return session_deferred

  def test_load_session_after_tls_handshake_session_not_found(self):
    """ This test makes sure that utilities.load_session_after_tls_handshake() correctly fails after receiving a request
    for a session that doesn't exist.
    """

    def raise_session_load_exception(res_id):
      """ This function raises a coordinator.SessionNotFound exception and is used to test error handling.
      """

      raise coordinator.SessionNotFound()

    # Create a mock protocol and session to test with
    test_res_id = "res_id"
    test_protocol = MagicMock()
    test_session = MagicMock()
    test_protocol.session_coordinator.load_reservation_session = raise_session_load_exception

    # Update the getPeerCertificate method to return a mock certificate
    test_cert = MagicMock()
    test_subject = MagicMock()
    test_subject.commonName = test_res_id
    test_cert.get_subject = lambda : test_subject
    test_protocol.transport.getPeerCertificate = lambda : test_cert

    # Try to load the session
    session_deferred = utilities.load_session_after_tls_handshake(test_protocol)

    return self.assertFailure(session_deferred, coordinator.SessionNotFound)
