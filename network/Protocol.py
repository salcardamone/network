###
### Python standard dependencies
###

###
### Third-party dependencies
###
import simpy
###
### Project dependencies
###
from .Radio import Radio, RadioPacket
from .ScheduleManager import ScheduleManager

class Protocol:
    """ Base protocol class for radio communications.

    Handles scheduling of radio events and managing what radio events need to take
    place in response to other events, whether received packets or external events.
    """

    def __init__(self, env : simpy.Environment, radio : Radio):
        """ Class constructor.

        Parameters
        ----------
            env :
                The simpy environment.
            radio :
                A radio that can be used by the protocol for communication.
        """
        self._env = env
        self._schedule_manager = ScheduleManager(
            self._env, transmit_cb=radio.transmit, receive_cb=radio.receive,
            handle_packet_cb=self.handle_packet
        )

    def handle_packet(self, packet : RadioPacket):
        """ Determine and schedule what happens upon the receipt of a packet.

        Parameters
        ----------
            packet :
                The data packet that has been received.
        """
        pass
