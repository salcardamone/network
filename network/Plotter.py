###
### Python standard dependencies
###
from typing import Iterable, Optional, Tuple
import logging
###
### Third-party dependencies
###
import numpy as np
import mplcursors
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.widgets import CheckButtons
from matplotlib.patches import Patch, Rectangle
from matplotlib.collections import PatchCollection
###
### Project dependencies
###
from .Node import Node
from .World import World
from .Radio import Radio

def packet_routing(
    nodes : Iterable[Node], world : World,
    start_time : Optional[int] = 0, plot_interval : Optional[int] = None
):
    """ Plot the inter-node communications over some interval.

    Parameters
    ----------
        nodes :
            The list of nodes that have participated in communications.
        world :
            The world in which the nodes were communicating.
        start_time :
            Simulation time at which to begin plotting. Optional; if not specified,
            will use zero time.
        plot_interval :
            Simulation interval, from start_time, over which to plot. Optional; if
            not specified, will plot all events from start_time.
    """
    # Mapping from event type to various things we'll use for plotting that event type:
    #     label   : The label to use for the the event type.
    #     format  : kwargs for formatting the rectangle representing the kwarg
    #     patches : List of rectangles of the event type.
    events = {
        Radio.RadioEvent.Status.SUCCESS_TX : {
            "label"   : "TX Success",
            "format"  : { "facecolor" : "seagreen", "edgecolor" : "black" },
            "patches" : []
        },
        Radio.RadioEvent.Status.SUCCESS_RX : {
            "label"   : "RX Success",
            "format"  : { "facecolor" : "firebrick", "edgecolor" : "black" },
            "patches" : []            
        },
        World.CollisionEvent.Status.COLLISION : {
            "label"   : "Collision",
            "format"  : { "facecolor" : "goldenrod", "edgecolor" : "black" },
            "patches" : []
        },
        Radio.RadioEvent.Status.NOTHING_RX : {
            "label"   : "RX Fail: Nothing",
            "format"  : { "facecolor" : "salmon", "edgecolor" : "black" },
            "patches" : []
        },
        Radio.RadioEvent.Status.DROPPED_MODE : {
            "label"   : "RX Fail: Mode",
            "format"  : { "facecolor" : "cyan", "edgecolor" : "black", "hatch" : "///" },
            "patches" : []
        },
        Radio.RadioEvent.Status.DROPPED_RSSI : {
            "label"   : "RX Fail: RSSI",
            "format"  : { "facecolor" : "violet", "edgecolor" : "black", "hatch" : "..." },
            "patches" : []
        }
    }
    
    fig, axs = plt.subplots(nrows=1, ncols=1)
    fig.canvas.manager.set_window_title("Inter-Node Communications")
    
    node_height = 1.0
    inter_node_height = 0.2

    axs.set_yticks(np.arange(
        start=inter_node_height + node_height / 2,
        stop=len(nodes) * node_height + inter_node_height,
        step=inter_node_height + node_height
    ))
    axs.set_yticklabels([node._name for node in nodes])
    axs.set_ylim(0, len(nodes) * (node_height + inter_node_height) + inter_node_height)
    axs.set_ylabel("Node")
    axs.set_xlabel("Simulation Time")
    
    def get_node_index(name : str) -> int:
        """ Get the index of a node in the iterable of nodes.

        Arguments
        ---------
            name :
                Name of the node we're looking for.

        Returns
        -------
            int :
                The index of the node we're looking for.
        """
        for node_idx, node in enumerate(nodes):
            if node._name == name:
                return node_idx
        raise RuntimeError(f"Node {name} is not in the list of provided nodes.")
    
    def event_rectangle_anchor(node_idx : int, start_time : int) -> Tuple[float, float]:
        """ Generate the anchor point (bottom right corner) of event rectangle.

        Arguments
        ---------
            node_idx :
                The node's index in the list of nodes being plotted.
            start_time :
                The start time of the event.

        Returns
        -------
            Tuple[float, float] :
                The (x,y) coordinate of the rectangle's anchor point.
        """
        return (
            start_time, inter_node_height + node_idx * (node_height + inter_node_height)
        )

    def generate_single_packet_rectangle(
        node_idx : int, event : Radio.RadioEvent
    ) -> Rectangle:
        """ Generate a rectangle displaying a single-packet event.

        Arguments
        ---------
            node_idx :
                The node's index in the list of nodes being plotted.
            event :
                The event we're generating a rectangle for.
        
        Returns
        -------
            Rectangle :
                The rectangle positioned appropriately for the event we're representing.
        """
        return Rectangle(
            xy=event_rectangle_anchor(node_idx, event.time - event.packet.duration),
            width=event.packet.duration, height=node_height,
            **events[event.status]["format"], label=f"{event}"
        )

    def generate_double_packet_rectangle(
        node_idx : int, event : World.CollisionEvent
    ) -> Rectangle:
        """ Generate a rectangle displaying an event involving two packets.

        Arguments
        ---------
            node_idx :
                The node's index in the list of nodes being plotted.
            event :
                The event we're generating a rectangle for.
        
        Returns
        -------
            Rectangle :
                The rectangle positioned approrpately for the event we're representing.
        """
        return Rectangle(
            xy=event_rectangle_anchor(node_idx, event.time),
            width=collision_event.packet_a.duration, height=node_height,
            **events[event.status]["format"], label=f"{event.packet_a}\n{event.packet_b}"
        )

    ###
    ### Transmit Events
    ###
    tx_event_types = [
        Radio.RadioEvent.Status.SUCCESS_TX
    ]
    for node_idx, node in enumerate(nodes):
        history = node._radio._tx_packet_history
        for event_type in tx_event_types:
            for tx_event in Radio.RadioEvent.get_events(history, event_type):
                events[event_type]["patches"].append(
                    axs.add_patch(generate_single_packet_rectangle(node_idx, tx_event))
                )

    ###
    ### Receive Events
    ###
    rx_event_types = [
        Radio.RadioEvent.Status.SUCCESS_RX,
        Radio.RadioEvent.Status.NOTHING_RX,
        Radio.RadioEvent.Status.DROPPED_MODE,
        Radio.RadioEvent.Status.DROPPED_RSSI,
    ]
    for node_idx, node in enumerate(nodes):
        history = node._radio._rx_packet_history
        for event_type in rx_event_types:            
            for rx_event in Radio.RadioEvent.get_events(history, event_type):
                events[event_type]["patches"].append(
                    axs.add_patch(generate_single_packet_rectangle(node_idx, rx_event))
                )

    ###
    ### Collision Events
    ###
    for collision_event in world._collision_packet_history:
        node_idx = get_node_index(collision_event.packet_a.dest())
        events[World.CollisionEvent.Status.COLLISION]["patches"].append(
            axs.add_patch(generate_double_packet_rectangle(node_idx, collision_event))
        )

    # Since matplotlib won't automatically adjust the axis to accomodate patches,
    # we do this at the end of all the plotting
    if plot_interval is None:
        axs.autoscale()
        axs.set_xlim(left=start_time)
    else:
        axs.set_xlim(left=start_time, right=plot_interval, auto=False)

    # Hover animations for each event we've plotted, giving a bit of text information
    mplcursors.cursor(hover=True).connect(
        "add", lambda sel: sel.annotation.set_text(sel.artist.get_label())
    )

    # Generate checkboxes that we can use to toggle whether events of a particular
    # type are plotted or not
    patches_by_label = {}
    actives = []
    colours = []
    for event_type in events.keys():
        if events[event_type]["patches"] is not []:
            patches_by_label[events[event_type]["label"]] = events[event_type]["patches"]
            actives.append(events[event_type]["patches"][0].get_visible())
            colours.append(events[event_type]["format"]["facecolor"])

    checkbox_axs = axs.inset_axes([0.0, 0.0, 0.12, 0.12])
    checkboxes = CheckButtons(
        ax=checkbox_axs, labels=patches_by_label.keys(),
        actives=actives, label_props={"color" : colours},
        frame_props={"edgecolor" : colours}, check_props={"facecolor" : colours}
    )

    def checkbox_callback(label : str):
        """ Callback for checkboxes once un/ticked; negates whether the patches of
        the given event type are displayed or not.

        Parameters
        ----------
            label :
                The patch type we're manipulating.
        """
        for patch in patches_by_label[label]:
            patch.set_visible(not patch.get_visible())
            patch.figure.canvas.draw_idle()
    checkboxes.on_clicked(checkbox_callback)
