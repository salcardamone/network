network
=======

What Do We Want To Do
---------------------
(1) Manage a set of mobile nodes. Accomodate fixed nodes.
(2) Have them communicate with one another wirelessly through the exchange of packets.
(3) Have some channel model which causes packet loss depending on node's environment
    and path to receiving nodes.
(4) Have nodes adjust dynamical state based on objective (a waypoint), vicinity to other
    nodes (avoid collision) or whatever other things might be reasonably expected to result
    in a node changing its dynamical state.
(5) Support data transfer protocols that allow the nodes to operate collectively
    (i.e. swarm behaviour).

How Do We Do It?
----------------
- Might make sense to use DES. Events would be node reaching a waypoint, nodes colliding,
  packet transmission/ reception, etc. Can just dead-reckon dynamics from event to event.
- This makes it difficult to model the ability to achieve objective (4). If nodes need to
  avoid a collision, there'll have to be some fine-grained dynamics (things like
  acceleration profiles to anticipate a collision and avoid it).
- Also, (3) might be difficult since we'll have to model ARQ. The latency associated with
  successfully getting a packet from one node to another could be fairly high, and we'll
  have to be constantly creating events for each exchange.
- Node has to be aware of its global position. Could be via GPS or some other method. Assume,
  at least for the start, that this is solved and the node knows this information.
- In initial implementation, node should be able to move and communication endlessly. May
  have to add battery models in later implementations.

- Alternatively, the application could be a dynamics simulator with some timestep that's
  small enough to allow for the dynamics we want to model.
- Communication is then just some additional thing that happens at each timestep. The issue
  is that communication has a different timescale to dynamics; we'd effectively have to
  choose a timestep that allows us to model the fastest-varying part of the simulation.
- For instance, if channel throughput is 10Mbps and each packet is 1kb, then assuming
  transmission is instantaneous, the packet will be received in 100 microseconds, which
  seems a little too small for the dynamics timescales.

- Maybe we can do both -- have a normal dynamics simulator and a DES communications simulator:

Dynamics Simulator
------------------
LOOP node = 1 : num_nodes:
   create any comms. schedules and pass to comms. simulator

LOOP timestep = 1 : num_timesteps:
  LOOP node = 1 : num_nodes:
    IF node communicates:
       pass communication event for node to comms. simulator
    pass dynamics event to comms. simulator for time timestep + 1

- The comms. simulator then just processes events.
  - Timestep events are handled by passing control back to the dynamics simulator which
    updates shared state containing node positions and creating new comms. events
    that are periodically scheduled.
  - Communications events are handled by:
    - Create event for time in future (propagation delay) for other node to receive packet
    - For receive event, probabilistically pass packet to receiving node depending on channel
    - Spawn any more events from ACKs or NACKs or whatever else we're using.

- Alternatively, can do all of this with DES. At start, create dynamics event for timestep
  in the future. When this event is executed, its final action is to create a new dynamics
  event for a further timestep in the future.