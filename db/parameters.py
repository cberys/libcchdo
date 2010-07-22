""" libcchdo.db.parameters
Ways to get parameters from databases.
"""


import sys

import libcchdo
import connect
import model
import model.legacy
import model.convert


def find_legacy_parameter(name):
    legacy = model.legacy
    session = legacy.session()
    legacy_parameter = session.query(legacy.Parameter).filter(
        legacy.Parameter.name == name).first()

    if not legacy_parameter:
        # Try aliases
        legacy_parameter = session.query(legacy.Parameter).filter(
            legacy.Parameter.alias.like('%%%s%%' % name)).first()
        
        if not legacy_parameter:
            # Try known overrides
            libcchdo.warn(("No legacy parameter found for '%s'. Falling back "
                           "on known override parameters.") % name)
            legacy_parameter = legacy.Parameter.find_known(name)
    else:
        try:
            legacy_parameter.display_order = \
                model.legacy.MYSQL_PARAMETER_DISPLAY_ORDERS[
                    legacy_parameter.name]
        except:
            legacy_parameter.display_order = sys.maxint

    return legacy_parameter


def find_by_mnemonic(name, allow_contrived=False):

    def get_contrived_parameter(name):
        parameter = model.std.Parameter(name)
        parameter.full_name = name
        parameter.format = '%11s'
        parameter.units = None
        parameter.bound_lower = None
        parameter.bound_upper = None
        parameter.units = None
        parameter.display_order = sys.maxint
        return parameter

    if name.startswith('_') and allow_contrived:
        return get_contrived_parameter(name)
    else:
        try:
            legacy_parameter = find_legacy_parameter(name)
            # std parameter
            #return model.std.session().query(model.std.Parameter).filter(
            #    model.std.Parameter.name == name).first()
            return model.convert.parameter(legacy_parameter)
        except:
            if allow_contrived:
                libcchdo.warn(('Conversion from legacy to std parameter '
                               'failed. Falling back to contrived.'))
                return get_contrived_parameter(name)

        return None

