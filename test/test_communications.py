###
### Python standard dependencies
###
import logging
import unittest
from typing import Iterable
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
from network.Plotter import packet_routing

class TestCommunications(unittest.TestCase):
    """ Test basic communications between nodes functions as expected.
    """
    
    def __init__(self, *args, **kwargs):
        """ Class constructor.
        """
        super(TestCommunications, self).__init__(*args, **kwargs)
        self.env = simpy.Environment()
        initialise_sim_logger(self.env, logging.INFO)
        logging.getLogger("matplotlib").setLevel(logging.CRITICAL)
        
        self.nodes = [
            Node(self.env, "A"),
            Node(self.env, "B"),
            Node(self.env, "C")
        ]
        self.world = World(self.env, self.nodes)
        
        self.duration = 5
        self.packets = {
            "A->B" : DataPacket(src="A", dest="B", contents="Hello from A!"),
            "A->C" : DataPacket(src="A", dest="C", contents="Hello from A!"),
            "B->A" : DataPacket(src="B", dest="A", contents="Hello from B!"),
            "B->C" : DataPacket(src="B", dest="C", contents="Hello from B!"),
            "C->A" : DataPacket(src="C", dest="A", contents="Hello from C!"),
            "C->B" : DataPacket(src="C", dest="B", contents="Hello from C!"),
            "A->X" : DataPacket(src="A", dest="All", contents="Hello from A!"),
            "B->X" : DataPacket(src="B", dest="All", contents="Hello from B!"),
            "C->X" : DataPacket(src="C", dest="All", contents="Hello from C!"),
        }

    @staticmethod
    def verify_radio_packet(
        event : Radio.RadioEvent, data : DataPacket, status : Radio.RadioEvent.Status
    ) -> bool:
        """ Verify that the data packet and radio event status within a radio event
        match the expected values.

        Parameters
        ----------
            event :
                The event we're scrutinising the contents of.
            data :
                The data packet the event's radio packet should contain.
            status :
                The event status we're expecting.
        
        Returns
        -------
            bool :
                True if the event contents match the expected, else false.
        """
        return (event.packet.data_packet == data) and (event.status == status)

    def verify_num_events(self, tx_events : Iterable[int], rx_events : Iterable[int]) -> bool:
        """ Verify that the number of radio events logged by each node matches expected.

        Parameters
        ----------
            tx_events :
                Number of TX events for each node.
            rx_events :
                Number of RX events for each node.

        Returns
        -------
            bool :
                True if number of TX and RX events matches number recorded by each node.
        """
        result = True
        for node_idx, node in enumerate(self.nodes):
            result = result                                                  and \
                (len(node._radio._tx_packet_history) == tx_events[node_idx]) and \
                (len(node._radio._rx_packet_history) == rx_events[node_idx])
        return result
            
    def test_unicast(self):
        """ Verify that sending a packet from one node to another elicits the
        correct response from nodes.
        """
        def run():
            """ Run the following communication sequence:
            
                0          5
            A : +--- RX ---+
            B : +== TX A ==+
            C : 
            """
            yield self.env.all_of([
                self.env.process(self.nodes[0]._radio.receive(self.duration + 1E-3)),
                self.env.process(
                    self.nodes[1]._radio.transmit(self.duration, self.packets["B->A"])
                )
            ])
        
        r = self.env.process(run())
        self.env.run()

        self.assertTrue(self.verify_num_events(tx_events=[0,1,0], rx_events=[1,0,0]))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[0]._radio._rx_packet_history[0], data=self.packets["B->A"],
            status=Radio.RadioEvent.Status.SUCCESS_RX
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[1]._radio._tx_packet_history[0], data=self.packets["B->A"],
            status=Radio.RadioEvent.Status.SUCCESS_TX
        ))

    def test_broadcast(self):
        """ Verify that broadcasting a packet from one node to all others elicits the
        correct response from nodes.
        """
        def run():
            """ Run the following communication sequence:
            
                0          5
            A : +--- RX ---+
            B : +--- RX ---+
            C : += TX ALL =+
            """
            yield self.env.all_of([
                self.env.process(self.nodes[0]._radio.receive(self.duration + 1E-3)),
                self.env.process(self.nodes[1]._radio.receive(self.duration + 1E-3)),
                self.env.process(
                    self.nodes[2]._radio.transmit(self.duration, self.packets["C->X"])
                )
            ])
        
        r = self.env.process(run())
        self.env.run()

        self.assertTrue(self.verify_num_events(tx_events=[0,0,1], rx_events=[1,1,0]))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[0]._radio._rx_packet_history[0], data=self.packets["C->X"],
            status=Radio.RadioEvent.Status.SUCCESS_RX
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[1]._radio._rx_packet_history[0], data=self.packets["C->X"],
            status=Radio.RadioEvent.Status.SUCCESS_RX
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[2]._radio._tx_packet_history[0], data=self.packets["C->X"],
            status=Radio.RadioEvent.Status.SUCCESS_TX
        ))

    def test_listening(self):
        """ Verify that listening for a packet without anything transmitting elicits
        the correct response from nodes.
        """
        def run():
            """ Run the following communication sequence:
            
                0          5
            A : +--- RX ---+
            B :
            C : +--- RX ---+
            """
            yield self.env.all_of([
                self.env.process(
                    self.nodes[0]._radio.receive(self.duration)
                ),
                self.env.process(
                    self.nodes[2]._radio.receive(self.duration)
                ),
            ])
        
        r = self.env.process(run())
        self.env.run()

        self.assertTrue(self.verify_num_events(tx_events=[0,0,0], rx_events=[1,0,1]))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[0]._radio._rx_packet_history[0], data=None,
            status=Radio.RadioEvent.Status.NOTHING_RX
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[2]._radio._rx_packet_history[0], data=None,
            status=Radio.RadioEvent.Status.NOTHING_RX
        ))

    def test_not_listening(self):
        """ Verify that transmission of a packet without anything listening elicits
        the correct response from nodes.
        """
        def run():
            """ Run the following communication sequence:
            
                0          5
            A : +== TX B ==+
            B :
            C : +== TX A ==+
            """
            yield self.env.all_of([
                self.env.process(
                    self.nodes[0]._radio.transmit(self.duration, self.packets["A->B"])
                ),
                self.env.process(
                    self.nodes[2]._radio.transmit(self.duration, self.packets["C->A"])
                )
            ])
        
        r = self.env.process(run())
        self.env.run()

        self.assertTrue(self.verify_num_events(tx_events=[1,0,1], rx_events=[1,1,0]))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[0]._radio._rx_packet_history[0], data=self.packets["C->A"],
            status=Radio.RadioEvent.Status.DROPPED_MODE
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[1]._radio._rx_packet_history[0], data=self.packets["A->B"],
            status=Radio.RadioEvent.Status.DROPPED_MODE
        ))

        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[0]._radio._tx_packet_history[0], data=self.packets["A->B"],
            status=Radio.RadioEvent.Status.SUCCESS_TX
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[2]._radio._tx_packet_history[0], data=self.packets["C->A"],
            status=Radio.RadioEvent.Status.SUCCESS_TX
        ))

    def test_collision(self):
        """ Verify that the collision between packets on the air elicits the correct
        response from nodes.
        """
        def run():
            """ Run the following communication sequence:
            
                0          5
            A : +--- RX ---+
            B : +== TX A ==+
            C : +== TX A ==+
            """
            yield self.env.all_of([
                self.env.process(
                    self.nodes[0]._radio.receive(self.duration + 1E-3)
                ),
                self.env.process(
                    self.nodes[1]._radio.transmit(self.duration, self.packets["B->A"])
                ),
                self.env.process(
                    self.nodes[2]._radio.transmit(self.duration, self.packets["C->A"])
                )
            ])

        r = self.env.process(run())
        self.env.run()

        self.assertTrue(self.verify_num_events(tx_events=[0,1,1], rx_events=[1,0,0]))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[0]._radio._rx_packet_history[0], data=None,
            status=Radio.RadioEvent.Status.NOTHING_RX
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[1]._radio._tx_packet_history[0], data=self.packets["B->A"],
            status=Radio.RadioEvent.Status.SUCCESS_TX
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[2]._radio._tx_packet_history[0], data=self.packets["C->A"],
            status=Radio.RadioEvent.Status.SUCCESS_TX
        ))

    def test_rssi(self):
        """ Verify that the transmission of a radio packet whose signal strength is lower
        than the threshold of the receiving node's radio elicits the correct response
        from nodes.
        """
        def run():
            """ Run the following communication sequence:
            
                0          5
            A : +--- RX ---+
            B :
            C : +== TX A ==+
            """
            self.nodes[0]._radio._threshold_rssi = 2.0
            yield self.env.all_of([
                self.env.process(
                    self.nodes[0]._radio.receive(self.duration + 1E-3)
                ),
                self.env.process(
                    self.nodes[2]._radio.transmit(self.duration, self.packets["C->A"])
                )
            ])

        r = self.env.process(run())
        self.env.run()

        self.assertTrue(self.verify_num_events(tx_events=[0,0,1], rx_events=[2,0,0]))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[0]._radio._rx_packet_history[0], data=self.packets["C->A"],
            status=Radio.RadioEvent.Status.DROPPED_RSSI
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[0]._radio._rx_packet_history[1], data=None,
            status=Radio.RadioEvent.Status.NOTHING_RX
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[2]._radio._tx_packet_history[0], data=self.packets["C->A"],
            status=Radio.RadioEvent.Status.SUCCESS_TX
        ))

    def test_partial(self):
        """ Verify that listening for only part of a transmitted packet's duration doesn't
        result in receiving the packet.
        """
        def run():
            """ Run the following communication sequence:
            
                0          5
            A : +--- RX ---+
            B :
            C :      +== TX A ==+
            """
            yield self.env.any_of([
                self.env.process(
                    self.nodes[0]._radio.receive(self.duration)
                ),
                self.env.timeout(2.5)
            ])
            yield self.env.process(
                self.nodes[2]._radio.transmit(self.duration, self.packets["C->A"])
            )

        r = self.env.process(run())
        self.env.run()

        self.assertTrue(self.verify_num_events(tx_events=[0,0,1], rx_events=[1,0,0]))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[0]._radio._rx_packet_history[0], data=None,
            status=Radio.RadioEvent.Status.NOTHING_RX
        ))
        self.assertTrue(self.verify_radio_packet(
            event=self.nodes[2]._radio._tx_packet_history[0], data=self.packets["C->A"],
            status=Radio.RadioEvent.Status.SUCCESS_TX
        ))
