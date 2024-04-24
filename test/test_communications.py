###
### Python standard dependencies
###
import logging
import unittest
###
### Third-party dependencies
###
import simpy
###
### Project dependencies
###
from network.Logger import initialise_sim_logger
from network.Packet import DataPacket
from network.Radio import RadioPacket
from network.Protocol import Protocol
from network.Node import Node
from network.World import World
from network.Radio import Radio

class TestCommunications(unittest.TestCase):
    """ Test basic communications between nodes functions as expected. More
    of an integration than a unit test.
    """
    
    def __init__(self, *args, **kwargs):
        """ Class constructor.
        """
        super(TestCommunications, self).__init__(*args, **kwargs)
        self.env = simpy.Environment()
        initialise_sim_logger(self.env, logging.DEBUG)
        
        self.nodes = [
            Node(self.env, "A"),
            Node(self.env, "B"),
            Node(self.env, "C")
        ]
        self.world = World(self.env, self.nodes)
        
    def test_packet_collision(self):
        """ Test the exchange of packets between nodes, and that collision of packets
        on-air is handled appropriately by the world that routes packets to destination
        node/s.
        """
        packet_duration = 5
        b_to_a = DataPacket(src="B", dest="A", contents="Hello from B!")
        c_to_a = DataPacket(src="C", dest="A", contents="Hello from C!")
        a_to_x = DataPacket(src="A", dest="All", contents="Hello from A!")
        c_to_x = DataPacket(src="C", dest="All", contents="Hello from C!")
        
        def run():
            """ Orchestrate transmission and receiving amongst node radios over testing
            period.

            Time   : 0          5         10         15         20         25
            Node A : +--- RX ---+--- RX ---+--- RX ---+          += TX ALL =+
            Node B :            +== TX A ==+== TX A ==+          +--- RX ---+
            Node C :                       +== TX A ==+= TX ALL =+--- RX ---+
            """
            self.env.process(self.nodes[0]._radio.receive(15))

            # Unicast
            yield self.env.timeout(5)
            yield self.env.process(self.nodes[1]._radio.transmit(packet_duration, b_to_a))

            # Collision
            yield self.env.all_of([
                self.env.process(self.nodes[1]._radio.transmit(packet_duration, b_to_a)),
                self.env.process(self.nodes[2]._radio.transmit(packet_duration, c_to_a))
            ])

            # Broadcast no listening
            yield self.env.process(self.nodes[2]._radio.transmit(packet_duration, c_to_x))

            # Broadcast
            # Receive a bit longer than transmit to make sure the radio doesn't stop
            # receiving before the transmission ends (concurrent events don't appear to
            # conclude in the order in which they're scheduled, so assume stochastic)
            yield self.env.all_of([
                self.env.process(self.nodes[1]._radio.receive(5 + 1E-3)),
                self.env.process(self.nodes[2]._radio.receive(5 + 1E-3)),
                self.env.process(self.nodes[0]._radio.transmit(packet_duration, a_to_x))
            ])

        r = self.env.process(run())
        self.env.run(until=100)

        self.assertEqual(len(self.nodes[0]._radio._tx_packet_history), 1)
        self.assertEqual(len(self.nodes[1]._radio._tx_packet_history), 2)
        self.assertEqual(len(self.nodes[2]._radio._tx_packet_history), 2)

        self.assertEqual(len(self.world._collision_packet_history), 1)
        self.assertEqual(self.world._collision_packet_history[0].time, 10)
        
        self.assertEqual(len(self.nodes[0]._radio._rx_packet_history), 2)
        self.assertEqual(len(self.nodes[1]._radio._rx_packet_history), 2)
        self.assertEqual(len(self.nodes[2]._radio._rx_packet_history), 1)

        self.assertEqual(
            len(Radio.PacketEvent.get_events(
                self.nodes[0]._radio._rx_packet_history,
                Radio.PacketEvent.Status.SUCCESS
            )), 1
        )
        self.assertEqual(
            len(Radio.PacketEvent.get_events(
                self.nodes[0]._radio._rx_packet_history,
                Radio.PacketEvent.Status.DROPPED_MODE
            )), 1
        )
        self.assertEqual(
            Radio.PacketEvent.get_events(
                self.nodes[0]._radio._rx_packet_history,
                Radio.PacketEvent.Status.DROPPED_MODE
            )[0].time, 15
        )
