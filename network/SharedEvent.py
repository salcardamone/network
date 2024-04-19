###
### Python standard dependencies
###
from typing import Optional, Any
###
### Third-party dependencies
###
import simpy
###
### Project dependencies
###


class SharedEvent:
    """ A simpy Event that can be shared across difference objects.

    The passivate/ reactivate pattern requires creation of a new simpy Event
    upon reactivation. If two objects share this event, reactivation by one
    object involves creation of a new simpy Event and assignment to a local
    variable that's supposed to be shared between objects, but this results
    in both objects holding different Events.

    Just a wrapper for a simpy Event, so that objects can hold the same
    SharedEvent, and access the same member variable contained within regardless
    of whether reactivation has taken place or not.
    """
    
    def __init__(self, env : simpy.Environment):
        """ Class constructor.

        Parameters
        ----------
            env :
                Simpy environment from which we'll create Events.
        """
        self._env = env
        self.event = self._env.event()

    def reactivate(self, value : Optional[Any] = None):
        """ Reactivate pattern for the held event.

        Trigger the event and pass in any values we want to give to the
        process waiting on this event.

        Parameters
        ----------
            value :
                Optional value we can pass to the object waiting on the
                event.
        """
        self.event.succeed(value=value)
        self.event = self._env.event()
