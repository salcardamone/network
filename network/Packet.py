###
### Python standard dependencies
###
from typing import Mapping, Callable, Iterable, Optional, Any
###
### Third-party dependencies
###

###
### Project dependencies
###


class DataPacket:
    """ A packet containing data to be passed between nodes.
    """

    def __init__(
        self, src : str, dest : str,
        fields : Optional[Mapping[str, Callable[[], str]]] = None,
        contents : Optional[Mapping[str, Any]] = None
    ):
        """ Class constructor.

        Parameters
        ----------
            src :
                The source node identifier.
            dest :
                The destination node identifier.
            fields :
                Mapping from field name to a callable (taking zero arguments --
                these should be bound by whatever's calling the constructor)
                which can be invoked to return the field's value. Optional,
                although either this or the `contents` parameter must be specified.
            contents :
                Mapping from field name to field value. Optional, although either
                this or the `fields` parameter must be specified.
        """
        if not ((fields is None) ^ (contents is None)):
            raise RuntimeError(
                "DataPacket must be instantiated with either fields or contents argument."
            )
            
        self._src = src
        self._dest = dest
            
        if fields is not None:
            self._contents = {}
            for field_name, field_val in fields.items():
                self._contents[field_name] = field_val()
        else:
            self._contents = contents

    def __str__(self) -> str:
        """ Stringify the data packet.

        Returns
        -------
            string
                The stringified data packet.
        """
        return f"Link: {self._src} -> {self._dest}, Contents: {self._contents}"
        
    def __eq__(self, other : "DataPacket") -> bool:
        """ Equality overload for two data packets.

        Parameters
        ----------
            other :
                The data packet we're comparing with.

        Returns
        -------
            bool
                True if the packets are equal, otherwise false.
        """
        return \
            (self._src == other._src)   and \
            (self._dest == other._dest) and \
            (self._contents == other._contents)
        
    def fields(self) -> Iterable[str]:
        """ Getter for the field names that are carried within the data packet.

        Returns
        -------
            Iterable[string]
                Iterable containing field names.
        """
        return self._contents.keys()

    def data(self) -> Mapping[str, Any]:
        """ Getter for the contents of the data packet.

        Returns
        -------
            Mapping[string, Any]
                Dictionary mapping from field name to field value.
        """
        return self._contents
