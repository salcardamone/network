###
### Python standard dependencies
###
import logging
###
### Third-party dependencies
###
import simpy
###
### Project dependencies
###
from .Radio import Radio
from .Protocol import Protocol

class Node:
    """ A node with various peripherals.
    """
    
    def __init__(self, env : simpy.Environment, name : str):
        """ Class constructor.

        Parameters
        ----------
            env :
                The simpy environment.
            name :
                A unique identifier of the node.
        """
        self._env = env
        self._name = name
        # TODO: Add as constructor argument; injection
        self._radio = Radio(self._env, self._name)
        self._protocol = Protocol(self._env, self._radio)
        
        self._logger = logging.getLogger(self._name)
