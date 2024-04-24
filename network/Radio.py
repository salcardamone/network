###
### Python standard dependencies
###
import logging
from enum import Enum
from collections import deque
from dataclasses import dataclass
from typing import Optional, Iterable
###
### Third-party dependencies
###
import simpy
###
### Project dependencies
###
from .SharedEvent import SharedEvent
from .Packet import DataPacket

class RadioMode(Enum):
    """ States that a radio may be in.
    """
    # The radio is off; neither transmitting nor receiving
    OFF = 0
    # The radio is in receive mode
    RX  = 1
    # The radio is in transmit mode
    TX  = 2

@dataclass
class RadioPacket:
    """ Packet which is exchanged between radios.
    """

    # The data packet that the radio packet wraps
    data_packet : DataPacket
    # Duration of the radio packet in simulation time
    duration    : int
    # Received signal strength indicator of the packet
    rssi        : float

    def __str__(self) -> str:
        """ Stringify the radio packet.

        Returns
        -------
            string
                The stringified radio packet.
        """
        return f"DataPacket: ({self.data_packet}), Duration: {self.duration}, RSSI: {self.rssi}"

    def __eq__(self, other : "RadioPacket") -> bool:
            """ Equality overload for two radio packets.

            Parameters
            ----------
                other :
                    The radio packet we're comparing with.

            Returns
            -------
                bool
                    True if the radio packets are equal, otherwise false.
            """
            return \
            (self.data_packet == other.data_packet) and \
            (self.duration == other.duration)       and \
            (self.rssi == other.rssi)
    
    def src(self) -> str:
        """ Getter for the source node identifier.

        Returns
        -------
            string
                Source node identifier.
        """
        return self.data_packet._src

    def dest(self) -> str:
        """ Getter for the destination node identifier.

        Returns
        -------
            string
                Destination node identifier.
        """
        return self.data_packet._dest
    
class Radio:
    """ Interface between a node and the world allowing the exchange of packets.
    """

    @dataclass
    class PacketEvent:
        """ Logging event, keeping track of the time at which a packet traverses
        the radio.
        """

        class Status(Enum):
            """
            """
            # Packet was delivered successfully
            SUCCESS = 1
            # Packet wasn't delivered because RSSI was too low
            DROPPED_RSSI = 2
            # Packet wasn't delivered because radio wasn't in RX mode
            DROPPED_MODE = 3
            
        # Status of the packet that has traversed the radio
        status : Status
        # The time at which the packet traverses the radio. For a transmitted packet,
        # this is the time at which the transmission has ended. For a received
        # packet, this is the time at which the packet has been received.
        time : int
        # The radio packet traversing the radio 
        packet : RadioPacket

        @staticmethod
        def get_events(
            events : Iterable["PacketEvent"], status : "Radio.PacketEvent.Status"
        ) -> Iterable["PacketEvent"]:
            """
            """
            return [packet for packet in events if packet.status == status]
        
        def __str__(self) -> str:
            """ Stringify the packet event.

            Returns
            -------
                string
                    The stringified packet event.
            """
            return f"Time: {self.time}, Status: {self.status}, RadioPacket: ({self.packet})"

        def __eq__(self, other : "PacketEvent") -> bool:
            """ Equality overload for two packet events.

            Parameters
            ----------
                other :
                    The packet event we're comparing with.

            Returns
            -------
                bool
                    True if the packet events are equal, otherwise false.
            """
            return \
                (self.status == other.status) and \
                (self.time == other.time)     and \
                (self.packet == other.packet)

            
    def __init__(self, env : simpy.Environment, node_name : str):
        """ Class constructor.

        Parameters
        ----------
            env :
                The simpy environement
            node_name :
                Name of the node owning the radio; allows us to create a logger
                with a useful name.
        """
        self._env = env
        self._logger = logging.getLogger(node_name + " Radio")
        # TODO: Inject this parameter
        self._threshold_rssi = 0.1
        
        self._mode = RadioMode.OFF
        # Event used to transmit packets to the world
        self._transmit_event = SharedEvent(self._env)
        # Event used to receive packets from the world
        self._receive_event = SharedEvent(self._env)
        # Process handle when the world has routed a packet to this radio
        # Before delivering packet, must timeout for the packet duration
        # so we can see whether any other packets will collide during
        # the on-air time
        self._pending_rx = None
        
        # Circular buffers holding transmitted and received packets
        self._tx_packet_history = deque(maxlen=100)
        self._rx_packet_history = deque(maxlen=100)
        
    def transmit(self, duration : int, packet : DataPacket):
        """ Transmit a packet; suspend the radio in transmit mode and
        pass the packet to the world for routing.

        Parameters
        ----------
            duration :
                Duration in simulation time of the packet.
            packet :
                The data packet we're sending.
        """
        self._mode = RadioMode.TX
        
        # TODO: Choose RSSI or tx power or whatever based on Radio parameter
        tx_packet = RadioPacket(
            data_packet=packet, duration=duration, rssi=1.0
        )
        self._transmit_event.reactivate(tx_packet)
        self._logger.debug(f"Begins TX. Packet: {tx_packet}")
        yield self._env.timeout(duration)

        self._mode = RadioMode.OFF
        
        self._tx_packet_history.append(
            self.PacketEvent(
                status=self.PacketEvent.Status.SUCCESS, time=self._env.now,
                packet=tx_packet
            )
        )
        self._logger.debug(f"Completes TX.")

    def notify_intent_to_deliver(self, packet : RadioPacket) -> bool:
        """ Check whether the delivery of a packet is feasible based on:

            (1) Whether the radio is in RX mode
            (2) The packet has an adequate RSSI

        Note that this does not guarantee that the delivery of the packet will
        succeed -- the world still needs to check whether the delivery of this
        packet collides with some other packet that similarly passes this check.
        
        Parameters
        ----------
            packet :
                The packet that's going to be attempted to be delivered.

        Returns
        -------
            bool
                True if the packet passes the checks outlined above, else false.
        """
        # If the radio isn't in RX mode, then we drop the packet 
        if self._mode != RadioMode.RX:
            self._rx_packet_history.append(
                self.PacketEvent(
                    status=self.PacketEvent.Status.DROPPED_MODE,
                    time=self._env.now, packet=packet
                )
            )
            self._logger.debug(self._rx_packet_history[-1])
            return False

        # Packet RSSI was too low to be received, so drop the packet
        if packet.rssi < self._threshold_rssi:
            self._rx_packet_history.append(
                self.PacketEvent(
                    status=self.PacketEvent.Status.DROPPED_RSSI,
                    time=self._env.now, packet=packet
                )
            )
            self._logger.debug(self._rx_packet_history[-1])
            return False

        # If we get to this point, there's nothing prohibiting our receiving the
        # packet, so we can affirm that we'll be able to try and receive the
        # packet
        return True
        
    def receive(self, duration : int) -> Optional[DataPacket]:
        """ Suspend the radio in receive mode for some scheduled duration; if
        a packet gets through, pass it onto the packet handler specified by
        the protocol.

        Parameters
        ----------
            duration :
                Duration in simulation time of the scheduled receive.

        Returns:
        --------
            Optional[DataPacket]
                The data packet we're received. If we didn't receive anything,
                will return None.
        """
        start_time = self._env.now
        end_time = self._env.now + duration
        self._mode = RadioMode.RX
        self._logger.debug(f"Begins RX. Will complete at {end_time}")

        packet = None
        # Keep receiving for the duration of the scheduled period; allows us to
        # ignore any dropped packets that have too low signal power and stay
        # listening in case another one comes in that the radio can hear
        while self._env.now < end_time:
            # We can either receive something or timeout on the scheduled receive
            # period
            receiving = self._receive_event.event
            listening = self._env.timeout(end_time - self._env.now)
            rx_packet = yield self._env.any_of([receiving, listening])

            if receiving in rx_packet:
                packet = receiving.value
                self._logger.debug(f"Receives Packet: {packet}")
                self._rx_packet_history.append(
                    self.PacketEvent(
                        status=self.PacketEvent.Status.SUCCESS,
                        time=self._env.now, packet=packet
                    )
                )
                packet = packet.data_packet
            else:
                # TODO: Need to create some unified interrupting data structure
                # for both radio turning off and packet collision
                if self._pending_rx != None and self._pending_rx.is_alive == True:
                    self._pending_rx.interrupt("Radio stopped being in receive mode!")
                else:
                    self._logger.debug("No packet was received.")
                
        self._logger.debug("Completes RX.")
        self._mode = RadioMode.OFF
        return packet
