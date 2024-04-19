###
### Python standard dependencies
###
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Union
###
### Third-party dependencies
###

###
### Project dependencies
###
from .Radio import RadioMode
from .Packet import DataPacket

class ScheduleState(Enum):
    """ States that a schedule may be in.
    """
    # The schedule is active and the schedule manager can use it when
    # evaulating which schedule executes next
    ACTIVE = 1
    # The schedule has completed and the schedule manager can remove it
    COMPLETE = 2
    # The schedule has been suspended and the schedule manager can ignore
    # it when evaluating which schedule executes next
    # TODO: Going from suspended -> active should modify the start field
    SUSPENDED = 3

@dataclass
class Schedule:
    """ A schedule for (repeating) radio events.
    """
    
    # Simulation time at which the schedule begins its first event
    start    : int
    # Amount of simulation time elapsed between start and end of
    # a single event
    duration : int
    # Amount of simulation time elapsed between starts of consecutive
    # events
    delay    : int
    # Number of events
    num      : int
    # What state the radio should be in for the schedule's events
    mode     : RadioMode
    # Constructor taking no arguments and returning a data packet that can
    # be invoked to create a packet when the schedule becomes active if
    # the schedule describes a transmission event. Optional, doesn't need
    # to be specified if the schedule describes a receive event.
    packet_constructor : Optional[Callable[[], DataPacket]] = None
    
    def __post_init__(self):
        """ Post-construction method to perform checks and setup internal state.
        """
        if self.duration > self.delay:
            raise RuntimeError(
                f"Inter-message delay ({self.delay}) in Schedule must " +
                f"be greater than or equal to message duration ({self.duration})."
            )
        if self.mode == RadioMode.TX and self.packet_constructor == None:
            raise RuntimeError(
                "Packet constructor can't be null when Schedule mode is TX."
            )

        self.state = ScheduleState.ACTIVE
        # Schedule counter; schedule repeats `num` times, and this tracks how
        # many times the schedule has thus far been active.
        self._current = 0
        
    def next_time(self) -> int:
        """ Compute the simulation time at which the next schedule event is to take place.

        Returns
        -------
            int
                Simulation time at which the schedule becomes active.
        """
        if self._current < self.num:
            return self.start + self._current * self.delay
        else:
            raise RuntimeError("Schedule has expired -- shouldn't be querying next_time().")

    def event(self) -> Union[DataPacket, "Schedule"]:
        """ Retrieve the data required for either transmission or receiving
        and increment the schedule counter.

        Note that this is a generator, and the caller should use next() when
        calling.

        Returns
        -------
            Union[DataPacket, Schedule]
                If the schedule is for transmission, will return the data packet to transmit.
                If the schedule is for receiving, will return this schedule so that receive
                duration can be retrieved by the radio.
        """
        return_val = None
        while self._current < self.num:
            self._current += 1

            if self.mode == RadioMode.TX:
                return_val = self.packet_constructor()
            elif self.mode == RadioMode.RX:
                return_val = self

            if self._current == self.num:
                self.state = ScheduleState.COMPLETE
            yield return_val
                
