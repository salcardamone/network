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
from network.Packet import DataPacket
from network.Radio import Radio, RadioMode, RadioPacket
from network.Schedule import Schedule
from network.ScheduleManager import ScheduleManager

class TestScheduling(unittest.TestCase):
    """ Various tests for Schedule and ScheduleManager classes.
    """
    
    def __init__(self, *args, **kwargs):
        """ Class constructor.

        Setup the logger and simpy environment that'll be used throughout.
        """
        super(TestScheduling, self).__init__(*args, **kwargs)
        self.env = simpy.Environment()
        initialise_sim_logger(self.env, logging.INFO)

    def test_schedule_increment(self):
        """ Verify that we can increment a Schedule for the requisite number
        of radio events, and that the packet generated conforms to what we
        expect.
        """
        num_packets = 5
        packet_start_time = 10
        inter_packet_delay = 20

        class DummyFunctor:
            """ Functor that increments state held within on every call.
            """

            def __init__(self):
                """ Class constructor.
                """
                self.var = 0
                
            def __call__(self):
                """ Overload of (); increment internal state and return it.
                """
                self.var += 1
                return self.var

        # Create a schedule whose packet generator invokes the above functor
        # to increment the field on each packet generation
        dummy_var = DummyFunctor()
        sched = Schedule(
            start=packet_start_time, duration=5, delay=inter_packet_delay,
            num=num_packets, mode=RadioMode.TX,
            packet_constructor=lambda: DataPacket(
                src="A", dest="B", fields={"Var" : dummy_var}
            )
        )

        def run():
            """ Invoke the schedule and generate a packet each time. Verify that the
            packet contains the expected contents each time, and that querying the
            Schedule when it expires results in the expected behaviour.
            """
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
        """ Verify that schedule managers are able to function and interact with
        radios as expected, i.e. packets can be exchanged between the radios that
        are drived by schedule managers.
        """
        def dummy_handler(packet: DataPacket):
            """ Dummy function which takes a received data packet and is meant to
            take some action based on it. Just count the number of times the
            function has been called.

            Parameters
            ----------
                packet :
                    The data packet to be handled.
            """
            if "counter" not in dummy_handler.__dict__:
                dummy_handler.counter = 0
            dummy_handler.counter += 1

        radio_a = Radio(self.env, "A")
        radio_b = Radio(self.env, "B")

        scheduler_a = ScheduleManager(
            self.env, radio_a.transmit, radio_a.receive, dummy_handler
        )
        scheduler_b = ScheduleManager(
            self.env, radio_b.transmit, radio_b.receive, dummy_handler
        )

        tx_packet = DataPacket(src="A", dest="B", fields={})
        # scheduler_a will transmit at times:
        # [10, 15], [30, 35], [50, 55], [70, 75], [90, 95]
        tx_start_time = 10
        tx_duration = 5
        tx_delay = 20
        tx_num = 5
        tx_sched = Schedule(
            start=tx_start_time, duration=tx_duration, delay=tx_delay,
            num=tx_num, mode=RadioMode.TX, packet_constructor=lambda: tx_packet
        )
        scheduler_a.add(tx_sched)
        # scheduler_b will listen at times:
        # [ 5, 20], [25, 40], [45, 60], [65, 80], [85, 100] 
        rx_start_time = 5
        rx_duration = 15
        rx_delay = 20
        rx_num = 5
        rx_sched = Schedule(
            start=rx_start_time, duration=rx_duration, delay=rx_delay, num=rx_num,
            mode=RadioMode.RX
        )
        scheduler_b.add(rx_sched)
        
        def run():
            """ Wait for a transmission event, timeout for the packet duration
            and pass the packet onto the listening radio.
            """
            for _ in range(tx_num):
                packet = yield radio_a._transmit_event.event
                yield self.env.timeout(tx_duration)
                radio_b._receive_event.reactivate(packet)

        r = self.env.process(run())
        self.env.run(until=150)

        # The transmitting radio should have transmitted 5 packets and
        # received none
        self.assertEqual(len(radio_a._tx_packet_history), tx_num)
        self.assertEqual(len(radio_a._rx_packet_history), 0)
        for tx_idx, tx_event in enumerate(radio_a._tx_packet_history):
            self.assertEqual(
                tx_event,
                Radio.PacketEvent(
                    status=Radio.PacketEvent.Status.SUCCESS,
                    time=tx_start_time + tx_duration + tx_idx*tx_delay,
                    packet=RadioPacket(
                        data_packet=tx_packet, duration=tx_duration, rssi=1.0
                    )
                )
            )

        # The listening radio should have received 5 packets and transmitted
        # none
        self.assertEqual(dummy_handler.counter, rx_num)
        self.assertEqual(len(radio_b._tx_packet_history), 0)
        self.assertEqual(len(radio_b._rx_packet_history), rx_num)
        for rx_idx, rx_event in enumerate(radio_b._rx_packet_history):
            self.assertEqual(
                rx_event,
                Radio.PacketEvent(
                    status=Radio.PacketEvent.Status.SUCCESS,
                    time=tx_start_time + tx_duration + rx_idx*tx_delay,
                    packet=RadioPacket(
                        data_packet=tx_packet, duration=tx_duration, rssi=1.0
                    )
                )
            )
