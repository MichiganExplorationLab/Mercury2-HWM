""" This module contains various utility classes and functions for testing the session system.
"""

# Import required modules
from mock import MagicMock

class MockSessionCoordinator(object):
  """ A mock session coordinator that provides enough functionality to test the command parser.
  """

  def __init__(self, command_parser):
    """ Sets up the mock session coordinator.
    """

    command_parser.session_coordinator = self

  def load_user_sessions(self, user_id):
    """ A mock of the SessionCoordinator.load_user_sessions() method that returns an array of active user Sessions.

    @param user_id  The ID of the user to load sessions for.
    @returns Returns an array consisting of a single mock session.
    """

    sessions = [MagicMock()]

    return sessions