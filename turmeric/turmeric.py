import copy
import sys


import numpy as np
import scipy as sp
import tabulate

# analyses
from . import dc
from . import transient
from . import ac

# parser
from . import netlist_parser

# misc
from . import constants
from . import utilities

# print result data
from . import printing

from .__version__ import __version__

global _queue, _x0s, _print

_print = False
_x0s = {None: None}

import logging

def run(circ, an_list=None):
    results = {}

    an_list = copy.deepcopy(an_list)
    if type(an_list) == tuple:
        an_list = list(an_list)
    elif type(an_list) == dict:
        an_list = [an_list] # run(mycircuit, op1)

    while len(an_list):
        an_item = an_list.pop(0)
        an_type = an_item.pop('type')
        if 'x0' in an_item and isinstance(an_item['x0'], str):
            logging.warning("%s has x0 set to %s, unavailable. Using 'None'." %
                                   (an_type.upper(), an_item['x0']))
            an_item['x0'] = None
        r = analysis[an_type](circ, **an_item)
        results.update({an_type: r})
        
    return results


def new_x0(circ, icdict):
    
    return dc.build_x0_from_user_supplied_ic(circ, icdict)


def icmodified_x0(circ, x0):
    
    return dc.modify_x0_for_ic(circ, x0)


def set_temperature(T):
    """Set the simulation temperature, in Celsius."""
    T = float(T)
    if T > 300:
        printing.print_warning("The temperature will be set to %f \xB0 C.")
    constants.T = utilities.Celsius2Kelvin(T)

analysis = {'op': dc.op_analysis, 'dc': dc.dc_analysis,
            'tran': transient.transient_analysis, 'ac': ac.ac_analysis,
            'temp': set_temperature}


def main(filename, outfile="stdout"):
    """
    filename : string
        The netlist filename.

    outfile : string, optional
        The output file's base name to which a suffix corresponding to the analysis performed will be added.
    - Alternate Current (AC): ``.ac``
    - Direct Current (DC): ``.dc``
    - Operating Point (OP): ``.opinfo``
    - TRANsient (TRAN): ``.tran``

    **Returns:**

    res : dict
        A dictionary containing the computed results.
    """
    logging.info("This is turmeric %s running with:" % __version__)
    logging.info("==Python %s" % (sys.version.split('\n')[0],))
    logging.info("==Numpy %s" % (np.__version__))
    logging.info("==Scipy %s" % (sp.__version__))
    logging.info("==Tabulate %s" % (tabulate.__version__))
    
    logging.info(f"Parsing netlist file `{filename}'")
    try:
        (circ, directives) = netlist_parser.parse_network(filename)
    except FileNotFoundError as e:
        logging.exception(f"{e}: netlist file {filename} was not found")
        sys.exit()
    except IOError as e:
        # TODO: verify that parse_network can throw IOError
        logging.exception(f"{e}: ioerror on netlist file {filename}")
        sys.exit()

    # TODO: Verify check_circuit is used
    #logging.info("Checking circuit for common mistakes...")
    # utility check should be member method for circuit class
    #(check, reason) = utilities.check_circuit(circ)
    #if not check:
    #    logging.error(reason)
    #    sys.exit(3)
    #logging.info("Finished")

    
    logging.info("Parsed circuit:")
    print(circ)
    logging.info("Models:")
    for m in circ.models:
        circ.models[m].print_model()

    ic_list = netlist_parser.parse_ics(directives)
    _handle_netlist_ics(circ, an_list=[], ic_list=ic_list)
    results = {}
    for an in netlist_parser.parse_analysis(circ, directives):
        if 'outfile' not in list(an.keys()) or not an['outfile']:
            an.update(
                {'outfile': outfile + ("." + an['type']) * (outfile != 'stdout')})
        _handle_netlist_ics(circ, [an], ic_list=[])
        
        logging.info("Requested an.:")
        # print to logger
        printing.print_analysis(an)
        
        results.update(run(circ, [an]))

    return results


def _handle_netlist_ics(circ, an_list, ic_list):
    for ic in ic_list:
        ic_label = list(ic.keys())[0]
        icdict = ic[ic_label]
        _x0s.update({ic_label: new_x0(circ, icdict)})
    for an in an_list:
        if 'x0' in an and isinstance(an['x0'], str):
            if an['x0'] in list(_x0s.keys()):
                an['x0'] = _x0s[an['x0']]
            elif an_list.index(an) == 0:
                raise ValueError(("The x0 '%s' is not available." % an["x0"]) +\
                                 (an['x0'] == 'op' or an['x0'] == 'op+ic')*
                                 " Perhaps you forgot to define an .OP?")

