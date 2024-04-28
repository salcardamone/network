###
### Python standard dependencies
###
from enum import Enum
import logging
from typing import Iterable
from dataclasses import dataclass
from collections import deque
###
### Third-party dependencies
###
import simpy
###
### Project dependencies
###
from .Node import Node
from .Radio import RadioMode, RadioPacket, Radio

class World:
    """ Environment in which nodes exist; includes features such as physical
    obstacles that may impact wireless communications and movement.
    """
    
    @dataclass
    class CollisionEvent:
        """ Logging event, keeping track of the time at which a collision between
        packets on-air takes place
        """

        class Status(Enum):
            """
            """
            # Packets collided on-air
            COLLISION = 1

        # Status of the collision event
        status : Status
        # The time at which the packets collide
        time : int
        # First packet being delivered
        packet_a : RadioPacket
        # Second packet being delivered
        packet_b : RadioPacket

        def __str__(self) -> str:
            """ Stringify the collision event.

            Returns
            -------
                string
                    The stringified collision event.
            """
            return f"Time: {self.time}, " \
                f"RadioPacket A: ({self.packet_a}), RadioPacket B: ({self.packet_b})"

        def __eq__(self, other : "CollisionEvent") -> bool:
            """ Equality overload for two collision events.

            Parameters
            ----------
                other :
                    The collision event we're comparing with.

            Returns
            -------
                bool
                    True if the collision events are equal, otherwise false.
            """
            # God only knows what order the packets get assigned in, so check
            # both permutations
            return \
                (self.time == other.time)          and \
                ((self.packet_a == other.packet_a) and \
                (self.packet_b == other.packet_b)) or  \
                ((self.packet_a == other.packet_b) and \
                self.packet_b == other.packet_a)
        
    def __init__(self, env : simpy.Environment, nodes : Iterable[Node]):
        """ Class constructor.

        Parameters
        ----------
            env :
                The simpy environment.
            nodes :
                List of nodes that are in the world.
        """
        self._env = env
        # Mapping from node name -> Node instance
        self._nodes = {}
        for node in nodes:
            self._nodes[node._name] = node

        self._comms_proc = self._env.process(self.communications())
        self._logger = logging.getLogger("World")

        # Circular buffer holding events where packets collide
        self._collision_packet_history = deque(maxlen=100)
        
    def communications(self):
        """ Run the communications process, routing transmitted messages between
        nodes.
        """
        while True:
            # Wait for any Node to try and transmit a packet
            tx_events = [node._radio._transmit_event.event for node in self._nodes.values()]
            tx_packets = yield self._env.any_of(tx_events)

            # For each Node trying to transmit a packet this timestep, route the packet
            for tx_packet in [packet.value for packet in tx_packets]:

                ## TODO : RSSI calculation

                # Work out which Nodes we need to route the packet to; need to check whether
                # it's a broadcast packet or not, and remove the transmitting Node from the
                # recipient list if so
                rx_nodes = []
                if tx_packet.dest() == "All":
                    rx_nodes = self._nodes.copy()
                    del rx_nodes[tx_packet.src()]
                    rx_nodes = list(rx_nodes.values())
                else:
                    rx_nodes = [self._nodes[tx_packet.dest()]]

                names = [node._name for node in rx_nodes]
                # Deliver the packet to the destination Nodes so long as the destination
                # node radios are capable of receiving the packet that's being routed
                for rx_node in rx_nodes:
                    if rx_node._radio.notify_intent_to_deliver(tx_packet):
                        pending_rx = rx_node._radio._pending_rx
                        # If the receiving Node isn't currently in the process of
                        # receiving an earlier packet, start receiving
                        if pending_rx == None or pending_rx.is_alive == False:
                            rx_node._radio._pending_rx = self._env.process(
                                self.pending_transmit(rx_node._radio, tx_packet)
                            )
                        # Otherwise if the receiving Node is in the process of receiving
                        # an earlier packet, interrupt that receive process and ascertain
                        # whether this new packet interferes with the receiving of the
                        # earlier packet
                        else:
                            if (pending_rx is not None) or pending_rx.is_alive == True:
                                pending_rx.interrupt(tx_packet)
                            else:
                                self._logger.warning("Unrecognised error when routing.")

    def pending_transmit(self, radio : Radio, packet : RadioPacket):
        """ Timeout for the duration of a radio packet.

        This should be spawned as a process belonging to the receiving node; if
        the world tries to deliver another packet while this process is running,
        then the process will being interrupted and both packets lost owing to
        their interference with one another.

        Parameters
        ----------
            packet :
                The packet that we're trying to deliver.
        """        
        start_time = self._env.now
        end_time = start_time + packet.duration
        collision = False

        # Keep listening till we've heard the entire packet
        while self._env.now < end_time:
            # Timeout for the entire packet's duration
            try:
                yield self._env.timeout(end_time - self._env.now)
            # TODO : Triggering this interrupt should update the end time to whichever
            #        of the packets has longer duration; can't just kill the process for
            #        another packet to immediately come along and think there's nothing
            #        else currently being received
            except simpy.Interrupt as interrupt:
                interrupting_packet = interrupt.cause
                if type(interrupting_packet) is RadioPacket:
                    self._logger.debug(
                        f"{interrupting_packet.data_packet} collides with {packet.data_packet}"
                    )
                    self._collision_packet_history.append(
                        self.CollisionEvent(
                            status=self.CollisionEvent.Status.COLLISION,
                            time=self._env.now, packet_a=interrupting_packet, packet_b=packet
                        )
                    )
                elif type(interrupting_packet) is str:
                    self._logger.debug(f"Interrupted: {interrupting_packet}")
                # Don't want to return yet because we want to mop up any other
                # packets that might collide with this one; just flag that
                # RX won't be successful
                collision = True

        # If we've got here, we've suspended for the entire packet duration and
        # no other packets have interfered with this one, so we can successfully
        # deliver
        if collision == False:
            radio._receive_event.reactivate(packet)
