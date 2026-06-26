import logger

from tornado import gen
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError

from config import config
from events import events
from envisalink import get_checksum


class Proxy(object):
    def __init__(self):
        if not getattr(config, 'ENABLEPROXY', True):
            logger.debug('Envisalink Proxy is disabled')
            return

        logger.info('Starting Envisalink Proxy on port ' + str(config.ENVISALINKPROXYPORT))
        
        self.proxy_server = ProxyServer()
        self.proxy_server.listen(config.ENVISALINKPROXYPORT)


class ProxyServer(TCPServer):
    def __init__(self):
        TCPServer.__init__(self)
        self.connections = {}          # fromaddr -> ProxyConnection

        # Rejestrujemy handler tak jak w oryginale
        events.register('proxy', self.proxy_event)

    @gen.coroutine
    def handle_stream(self, stream, address):
        fromaddr = "%s:%s" % (address[0], address[1])
        logger.info('Proxy Client connected: ' + fromaddr + ' | Active: ' + str(len(self.connections) + 1))

        connection = ProxyConnection(stream, address, self)
        self.connections[fromaddr] = connection

        try:
            yield connection.on_connect()
        finally:
            if fromaddr in self.connections:
                del self.connections[fromaddr]
            logger.info('Proxy Client disconnected: ' + fromaddr + ' | Active: ' + str(len(self.connections)))

    @gen.coroutine
    def proxy_event(self, zone, parameters, input):
        """Oryginalna logika broadcastu"""
        if not self.connections:
            return

        for fromaddr, conn in list(self.connections.items()):
            try:
                if conn.authenticated:           # tylko zalogowani klienci
                    yield conn.send_raw(input)
            except:
                pass


class ProxyConnection(object):
    def __init__(self, stream, address, server):
        self.stream = stream
        self.address = address
        self.server = server
        self.authenticated = False

        self.stream.set_close_callback(self.on_disconnect)
        self.send_command('5053')   # Request password

    @gen.coroutine
    def on_connect(self):
        yield self.dispatch_client()

    @gen.coroutine
    def on_disconnect(self):
        pass

    @gen.coroutine
    def dispatch_client(self):
        try:
            while True:
                line = yield self.stream.read_until(b'\r\n')
                line_str = line.strip()

                if not line_str:
                    continue

                if self.authenticated:
                    events.put('envisalink', None, line)   # oryginalna logika
                else:
                    expected = '005' + config.ENVISALINKPROXYPASS + get_checksum('005', config.ENVISALINKPROXYPASS)
                    if line_str == expected:
                        logger.info('Proxy User Authenticated: ' + str(self.address[0]) + ':' + str(self.address[1]))
                        self.authenticated = True
                        self.send_command('5051')
                    else:
                        logger.warning('Proxy Authentication failed from ' + str(self.address[0]) + ':' + str(self.address[1]))
                        self.send_command('5050')
                        self.stream.close()
                        break
        except StreamClosedError:
            pass
        except Exception as e:
            logger.error('Client error: ' + str(e))

    @gen.coroutine
    def send_command(self, data, checksum=True):
        if checksum:
            to_send = data + get_checksum(data, '') + '\r\n'
        else:
            to_send = data + '\r\n'

        try:
            yield self.stream.write(to_send)
            logger.debug('PROXY < ' + to_send.strip())
        except:
            pass

    @gen.coroutine
    def send_raw(self, data):
        try:
            yield self.stream.write(data)
        except:
            pass
