###
### Python standard dependencies
###
import logging
from dataclasses import dataclass
from typing import Callable, Optional
###
### Third-party dependencies
###
import simpy
import numpy as np
###
### Project dependencies
###
from .SharedEvent import SharedEvent
from .Radio import RadioMode
from .Packet import DataPacket
from .Schedule import Schedule, ScheduleState

class ScheduleManager:
    """
    """

    @dataclass
    class ScheduleEvent:
        start : int
        stop : int
        mode : RadioMode

    def __init__(
        self, env : simpy.Environment,
        transmit_cb : Callable[[Schedule, DataPacket], None],
        receive_cb : Callable[[Schedule], DataPacket],
        handle_packet_cb : Callable[[Optional[DataPacket]], None]
    ):
        """
        """
        self._env = env
        self._logger = logging.getLogger("ScheduleManager")

        self._transmit_cb = transmit_cb
        self._receive_cb = receive_cb
        self._handle_packet_cb = handle_packet_cb
        
        self._schedules = []
        self._event_log = []
        self._awaiting_schedules = SharedEvent(env=self._env)
        
        self._manager_proc = self._env.process(self.run())
        
    def add(self, schedule : Schedule):
        """
        """
        was_awaiting_schedules = False
        if self._schedules == []:
            was_awaiting_schedules = True

        self._schedules.append(schedule)
        self._manager_proc.interrupt()
        
        self._event_log += [
            self.ScheduleEvent(
                start=start, stop=start + schedule.duration, mode=schedule.mode
            )
            for start in np.arange(0, schedule.num) * schedule.delay + schedule.start
        ]
        
        if was_awaiting_schedules:
            self._awaiting_schedules.reactivate()
        self._logger.debug(f"Schedule was added at time {self._env.now}")
        self._logger.debug(f"{schedule}")
        self._logger.debug(f"{len(self._schedules)} schedule/s are now active")
            
    def _next_active_schedule(self):
        """
        """
        if self._schedules == []:
            return None
        return min(self._schedules, key=lambda x : x.next_time())

    def run(self):
        """
        """
        while True:
            if self._schedules == []:
                yield self._awaiting_schedules.event

            # Wait till the next schdeule becomes active
            # Note that this can be interrupted in the case that the Schedule
            # list is manipulated somehow, e.g. addition of a schedule
            next_schedule = self._next_active_schedule()
            try:
                yield self._env.timeout(next_schedule.next_time() - self._env.now)
            except simpy.Interrupt as interrupt:
                self._logger.debug("Manager run process was interrupted.")
                continue

            # If we didn't prematurely interrupt the timeout till the next
            # schedule becomes active, then execute the asssociated event
            if next_schedule.next_time() == self._env.now:
                if next_schedule.mode == RadioMode.TX:
                    self._env.process(
                        self._transmit_cb(next_schedule.duration, next(next_schedule.event()))
                    )
                elif next_schedule.mode == RadioMode.RX:
                    rx_packet_event = yield self._env.process(
                        self._receive_cb(next(next_schedule.event()).duration)
                    )
                    self._handle_packet_cb(rx_packet_event)
                
                # Schedule has been enacted; process list of schedules
                if next_schedule.state == ScheduleState.COMPLETE:
                    self._schedules.remove(next_schedule)

