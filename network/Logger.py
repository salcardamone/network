###
### Python standard dependencies
###
import logging
from functools import partial
###
### Third-party dependencies
###
import simpy
###
### Project dependencies
###


def initialise_sim_logger(env: simpy.Environment, logger_level: int):
    logging.basicConfig(
        force=True,
        level=logger_level,
        format="%(name)-10s:Time %(asctime)-12s:%(levelname)-6s:%(message)s"
    )

    def sim_time(env: simpy.Environment, self, record, datefmt=None):
        return env.now
    logging.Formatter.formatTime = partial(sim_time, env)
