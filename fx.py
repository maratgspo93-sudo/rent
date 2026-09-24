import os

def get_rate():
    """USD->AMD։ վերցվում է FX_USD_AMD միջավայրի փոփոխականից։
    TODO: միացրեք ՀՀ ԿԲ-ի պաշտոնական փոխարժեքին (cba.am) և թարմացրեք օրը մեկ անգամ։"""
    return float(os.getenv("FX_USD_AMD", "385"))
