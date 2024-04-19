###
### Python standard dependencies
###
import logging
import unittest
from functools import partial
###
### Third-party dependencies
###
import simpy
###
### Project dependencies
###
from network.Logger import initialise_sim_logger
from network.SharedEvent import SharedEvent
from network.Schedule import Schedule
from network.Protocol import Protocol
from network.Radio import RadioMode
from network.ScheduleManager import ScheduleManager
from network.Packet import DataPacket
from network.Radio import Radio, RadioPacket

class TestScheduling(unittest.TestCase):
    """
    """
    
    def __init__(self, *args, **kwargs):
        """
        """
        super(TestScheduling, self).__init__(*args, **kwargs)
        self.env = simpy.Environment()
        initialise_sim_logger(self.env, logging.INFO)

    def test_timing(self):
        """
        """
        num_packets = 5
        packet_start_time = 10
        inter_packet_delay = 20

        class DummyFunctor:
            def __init__(self):
                self.var = 0
                
            def __call__(self):
                self.var += 1
                return self.var

        dummy_var = DummyFunctor()
        sched = Schedule(
            start=packet_start_time, duration=5, delay=inter_packet_delay,
            num=num_packets, mode=RadioMode.TX,
            packet_constructor=lambda: DataPacket(
                src="A", dest="B", fields={"Var" : dummy_var}
            )
        )

        def run():
            for packet_idx in range(num_packets):
                self.assertEqual(
                    sched.next_time(), packet_start_time + packet_idx * inter_packet_delay
                )
                yield self.env.timeout(sched.next_time() - self.env.now)
                scheduled_packet = next(sched.event())
                self.assertEqual(
                    scheduled_packet,
                    DataPacket(src="A", dest="B", contents={"Var" : packet_idx + 1})
                )
            self.assertRaises(RuntimeError, sched.next_time)
                
        r = self.env.process(run())
        self.env.run(until=150)

    def test_manager(self):
        """
        """
        def dummy_handler(packet: DataPacket):
            pass

        radio_a = Radio(self.env, "A")
        radio_b = Radio(self.env, "B")

        scheduler_a = ScheduleManager(
            self.env, radio_a.transmit, radio_a.receive, dummy_handler
        )
        scheduler_b = ScheduleManager(
            self.env, radio_b.transmit, radio_b.receive, dummy_handler
        )

        tx_packet = DataPacket(src="A", dest="B", fields={})
        tx_sched = Schedule(
            start=10, duration=5, delay=20, num=5, mode=RadioMode.TX,
            packet_constructor=lambda: tx_packet
        )
        rx_sched = Schedule(
            start=5, duration=15, delay=20, num=5, mode=RadioMode.RX
        )

        scheduler_a.add(tx_sched)
        scheduler_b.add(rx_sched)
        
        def run():
            for _ in range(5):
                packet = yield radio_a._transmit_event.event
                yield self.env.timeout(5)
                radio_b._receive_event.reactivate(packet)

        r = self.env.process(run())
        self.env.run(until=150)

        self.assertEqual(len(radio_a._tx_packet_history), 5)
        self.assertEqual(len(radio_a._rx_packet_history), 0)
        for tx_idx, tx_event in enumerate(radio_a._tx_packet_history):
            self.assertEqual(
                tx_event,
                Radio.PacketEvent(
                    status=Radio.PacketEvent.Status.SUCCESS,
                    time=15 + tx_idx*20, packet=RadioPacket(
                        data_packet=tx_packet, duration=5, rssi=1.0
                    )
                )
            )

        self.assertEqual(len(radio_b._tx_packet_history), 0)
        self.assertEqual(len(radio_b._rx_packet_history), 5)
        for rx_idx, rx_event in enumerate(radio_b._rx_packet_history):
            self.assertEqual(
                rx_event,
                Radio.PacketEvent(
                    status=Radio.PacketEvent.Status.SUCCESS,
                    time=15 + rx_idx*20, packet=RadioPacket(
                        data_packet=tx_packet, duration=5, rssi=1.0
                    )
                )
            )
