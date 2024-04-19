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
    """
    """
    
    def __init__(self, *args, **kwargs):
        """
        """
        super(TestCommunications, self).__init__(*args, **kwargs)
        self.env = simpy.Environment()
        initialise_sim_logger(self.env, logging.INFO)
        
        self.nodes = [
            Node(self.env, "A"),
            Node(self.env, "B"),
            Node(self.env, "C")
        ]
        self.world = World(self.env, self.nodes)
        
    def test_a(self):
        """
        """
        packet_duration = 5
        a_to_b = DataPacket(src="A", dest="B", contents="Hello!")
        c_to_b = DataPacket(src="C", dest="B", contents="Hello!")

        def run():
            self.env.process(self.nodes[1]._radio.receive(15))
            yield self.env.timeout(5)
            self.env.process(self.nodes[0]._radio.transmit(packet_duration, a_to_b))
            yield self.env.timeout(5)
            self.env.process(self.nodes[0]._radio.transmit(packet_duration, a_to_b))
            self.env.process(self.nodes[2]._radio.transmit(packet_duration, c_to_b))
            yield self.env.timeout(5)
            self.env.process(self.nodes[0]._radio.transmit(packet_duration, a_to_b))
            yield self.env.timeout(11)

        r = self.env.process(run())
        self.env.run(until=100)

        self.assertEqual(
            len(self.nodes[0]._radio._tx_packet_history), 3
        )
        self.assertEqual(
            self.nodes[0]._radio._tx_packet_history[0],
            Radio.PacketEvent(
                status=Radio.PacketEvent.Status.SUCCESS, time=10,
                packet=RadioPacket(data_packet=a_to_b, duration=packet_duration, rssi=1.0)
            )
        )
        self.assertEqual(
            len(self.world._collision_packet_history), 1
        )
        self.assertEqual(
            self.world._collision_packet_history[0],
            World.CollisionEvent(
                time=10,
                packet_a=RadioPacket(
                    data_packet=a_to_b, duration=packet_duration, rssi=1.0
                ),
                packet_b=RadioPacket(
                    data_packet=c_to_b, duration=packet_duration, rssi=1.0
                )
            )
        )
