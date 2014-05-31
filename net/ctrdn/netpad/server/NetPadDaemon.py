import ConfigParser
import NetPadConstants

__author__ = 'Lubomir Kaplan <castor@castor.sk>'
__version__ = "1.0.0"


class NetPadDaemon:
    def __init__(self):
        return
    

def _process_error(message, e):
    msg = "[ERROR] " + message
    print(msg)
    print("-"[:1]*len(msg))
    print(e)


def main():
    try:
        config = ConfigParser.ConfigParser()
        config.read(NetPadConstants.NetPadConstants.CONFIGURATION_FILE_NAME)
    except ConfigParser.ParsingError as e:
        _process_error("Unable to load NetPadDaemon configuration", e)


if __name__ == "__main__":
    main()